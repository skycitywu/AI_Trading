#!/usr/bin/env python3
"""定时守护进程 — 交易时段自动扫描

用法:
    python scripts/run_daemon.py                # 扫描所有监控标的
    python scripts/run_daemon.py --etf          # 只扫描 ETF 期权
    python scripts/run_daemon.py --commodity    # 只扫描商品期权
    python scripts/run_daemon.py --code 510050  # 扫描指定标的
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import logging
import signal
import sys
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.instruments import WATCHED_UNDERLYINGS
from config.settings import Settings
from src.analyst.llm_factory import create_llm
from src.fetcher.akshare_fetcher import AKShareFetcher
from src.models.signal import AnalysisResult, TradingSignal
from src.notify.formatter import format_scan_round
from src.notify.dispatcher import send_notify
from src.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger("daemon")

CST = ZoneInfo("Asia/Shanghai")
MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)

# 单次扫描超时（秒）。akshare 内部无超时参数，必须在外层兜底，
# 否则一次卡死的 HTTP 请求会让 APScheduler 因 max_instances=1 永远跳过后续任务。
SCAN_TIMEOUT_SECONDS = 600

# ── 去重状态 ──
_seen_signals: set[str] = set()
_dedup_date: date | None = None


def is_trading_hours() -> bool:
    """判断当前是否在 A 股交易时段（上海时间）"""
    now = datetime.now(CST)
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return (MORNING_START <= t <= MORNING_END) or (AFTERNOON_START <= t <= AFTERNOON_END)


def _signal_fingerprint(sig: TradingSignal) -> str:
    """基于内容的信号指纹，用于去重"""
    leg_codes = sorted(f"{leg.direction}:{leg.code}" for leg in sig.legs)
    raw = f"{sig.underlying}|{sig.action}|{','.join(leg_codes)}|{sig.confidence}"
    return hashlib.md5(raw.encode()).hexdigest()


def _reset_dedup_if_new_day():
    """新交易日清空去重缓存"""
    global _seen_signals, _dedup_date
    today = datetime.now(CST).date()
    if _dedup_date != today:
        _seen_signals = set()
        _dedup_date = today
        logger.info(f"去重缓存已重置 (新日期: {today})")


def setup_logging():
    """配置日志：终端 INFO + 每日文件 DEBUG"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    today = datetime.now(CST).strftime("%Y%m%d")
    log_file = log_dir / f"daemon_{today}.log"

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    logger.info(f"日志文件: {log_file.resolve()}")


def filter_targets(args) -> list:
    """根据 CLI 参数过滤标的"""
    targets = WATCHED_UNDERLYINGS
    if args.code:
        targets = [u for u in targets if u.code == args.code]
        if not targets:
            logger.error(f"未找到标的: {args.code}")
            sys.exit(1)
    elif args.etf:
        targets = [u for u in targets if u.market == "etf_option"]
    elif args.commodity:
        targets = [u for u in targets if u.market == "commodity_option"]
    return targets


def run_scan(pipeline: PipelineOrchestrator, targets: list):
    """单次扫描周期 — 由 APScheduler 定时调用"""
    now = datetime.now(CST)

    if not is_trading_hours():
        logger.info(f"非交易时段 ({now.strftime('%H:%M')} CST)，跳过扫描")
        return

    logger.info(f"{'='*50}")
    logger.info(f"开始定时扫描 ({now.strftime('%Y-%m-%d %H:%M')} CST)")

    _reset_dedup_if_new_day()

    # 每次扫描用独立的一次性 executor，超时后即便线程卡死也只是泄漏一个 daemon 线程，
    # 不会回过头来阻塞下一次扫描（这是上一次 4/24 卡死后整月不推送的根因）。
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="scan"
    )
    future = executor.submit(pipeline.scan_all, targets, False)
    executor.shutdown(wait=False)  # 不等待，超时的线程让它自生自灭
    try:
        results = future.result(timeout=SCAN_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        logger.error(f"扫描超时（>{SCAN_TIMEOUT_SECONDS}s），放弃本轮")
        try:
            send_notify(f"⚠️ AI Trading 扫描超时（>{SCAN_TIMEOUT_SECONDS}s），本轮已放弃")
        except Exception:
            pass
        return
    except Exception as e:
        logger.error(f"扫描异常: {e}", exc_info=True)
        return

    # 去重后合并发送通知
    total_new = 0
    total_dup = 0
    notify_results = []
    for result in results:
        new_signals = []
        for sig in result.signals:
            fp = _signal_fingerprint(sig)
            if fp not in _seen_signals:
                _seen_signals.add(fp)
                new_signals.append(sig)

        dup_count = len(result.signals) - len(new_signals)
        total_new += len(new_signals)
        total_dup += dup_count

        if new_signals:
            deduped = AnalysisResult(
                underlying=result.underlying,
                market_assessment=result.market_assessment,
                signals=new_signals,
                no_action_reasons=result.no_action_reasons,
                raw_response=result.raw_response,
                created_at=result.created_at,
            )
            notify_results.append(deduped)
            logger.info(
                f"{result.underlying}: {len(new_signals)} 个新信号"
                f" (过滤 {dup_count} 个重复)"
            )
        elif result.signals:
            logger.info(
                f"{result.underlying}: {len(result.signals)} 个信号均已推送过，跳过"
            )

    if notify_results:
        message = format_scan_round(notify_results)
        send_notify(message)

    logger.info(f"扫描完成: {len(results)} 个标的, {total_new} 个新信号, {total_dup} 个重复过滤")


def main():
    parser = argparse.ArgumentParser(description="AI 期权交易信号守护进程")
    parser.add_argument("--etf", action="store_true", help="只扫描 ETF 期权")
    parser.add_argument("--commodity", action="store_true", help="只扫描商品期权")
    parser.add_argument("--code", type=str, help="扫描指定标的代码")
    args = parser.parse_args()

    setup_logging()

    settings = Settings()
    targets = filter_targets(args)
    target_names = ", ".join(u.name for u in targets)

    logger.info(f"监控标的: [{target_names}]")
    logger.info(f"扫描间隔: {settings.scan_interval_minutes} 分钟")

    # 初始化组件
    fetcher = AKShareFetcher()
    llm = create_llm()
    pipeline = PipelineOrchestrator(fetcher=fetcher, llm=llm)

    # 调度器
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_scan,
        IntervalTrigger(minutes=settings.scan_interval_minutes),
        args=[pipeline, targets],
        id="scan",
        max_instances=1,
        coalesce=True,
    )

    # 优雅退出
    def shutdown(signum, frame):
        logger.info("收到退出信号，正在关闭...")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # 启动通知
    send_notify(
        f"🤖 AI Trading 守护进程已启动\n"
        f"扫描间隔: {settings.scan_interval_minutes} 分钟\n"
        f"监控标的: {target_names}"
    )

    # 立即执行一次扫描
    run_scan(pipeline, targets)

    # 开始定时调度
    try:
        logger.info("定时调度已启动，等待下一次扫描...")
        scheduler.start()
    finally:
        send_notify("🛑 AI Trading 守护进程已停止")
        logger.info("守护进程已退出")


if __name__ == "__main__":
    main()
