#!/usr/bin/env python3
"""手动单次扫描 — 测试端到端流水线

用法:
    python scripts/run_once.py                # 扫描所有监控标的
    python scripts/run_once.py --etf          # 只扫描 ETF 期权
    python scripts/run_once.py --commodity    # 只扫描商品期权
    python scripts/run_once.py --code 510050  # 扫描指定标的
"""

import argparse
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.instruments import WATCHED_UNDERLYINGS, Underlying
from src.analyst.llm_factory import create_llm
from src.fetcher.akshare_fetcher import AKShareFetcher
from src.pipeline.orchestrator import PipelineOrchestrator


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="AI 期权交易信号扫描")
    parser.add_argument("--etf", action="store_true", help="只扫描 ETF 期权")
    parser.add_argument("--commodity", action="store_true", help="只扫描商品期权")
    parser.add_argument("--code", type=str, help="扫描指定标的代码")
    parser.add_argument("--dry-run", action="store_true", help="只获取数据，不调用 LLM")
    parser.add_argument("--mock-llm", action="store_true", help="用 mock LLM 测试全流程")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("run_once")

    # 选择标的
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

    logger.info(f"扫描标的: {[u.name for u in targets]}")

    # 初始化组件
    fetcher = AKShareFetcher()

    if args.dry_run:
        # dry-run: 只测试数据获取
        for u in targets:
            logger.info(f"\n{'='*50}\n测试获取: {u.name}")
            chain = fetcher.fetch_option_chain(u)
            total = len(chain.calls) + len(chain.puts)
            logger.info(f"  标的价格: {chain.underlying.price}")
            logger.info(f"  期权合约数: {total} (calls={len(chain.calls)}, puts={len(chain.puts)})")
            if chain.calls:
                c = chain.calls[0]
                logger.info(f"  示例合约: {c.code}, 价格={c.last_price}, IV={c.iv}, Delta={c.greeks.delta}")

            history = fetcher.fetch_underlying_history(u, days=60)
            logger.info(f"  历史数据: {len(history)} 条")
        return

    # 完整流水线
    if args.mock_llm:
        from src.analyst.base_llm import BaseLLM

        class MockLLM(BaseLLM):
            def chat(self, system_prompt: str, user_prompt: str) -> str:
                return '''{
                    "market_assessment": "[Mock] 当前50ETF价格2.90，IV处于中等水平，市场波动率温和。短期趋势偏中性，无明显方向性机会。",
                    "signals": [],
                    "no_action_reasons": ["Mock模式: 真实分析需要配置LLM API key"]
                }'''

        llm = MockLLM()
    else:
        llm = create_llm()
    pipeline = PipelineOrchestrator(fetcher=fetcher, llm=llm)

    results = pipeline.scan_all(targets)

    # 汇总
    logger.info(f"\n{'='*50}")
    logger.info(f"扫描完成: {len(results)}/{len(targets)} 个标的成功")
    total_signals = sum(len(r.signals) for r in results)
    logger.info(f"共发现 {total_signals} 个交易信号")


if __name__ == "__main__":
    main()
