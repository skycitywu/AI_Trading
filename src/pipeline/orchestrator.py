"""流水线编排器 — 串联 数据获取 → 指标计算 → LLM决策 → 通知 四个阶段"""

from __future__ import annotations

import logging

from config.instruments import Underlying
from src.analyst.base_llm import BaseLLM
from src.analyst.context_builder import build_market_snapshot, snapshot_to_json
from src.analyst.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.analyst.signal_parser import parse_llm_response
from src.compute.screener import screen_candidates
from src.compute.technicals import calc_ma
from src.compute.volatility import (
    calc_historical_volatility,
    calc_iv_percentile,
    calc_iv_rank,
)
from src.fetcher.base import BaseFetcher
from src.models.market import VolatilityData
from src.models.signal import AnalysisResult
from src.notify.formatter import format_analysis
from src.notify.dispatcher import send_notify

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self, fetcher: BaseFetcher, llm: BaseLLM):
        self.fetcher = fetcher
        self.llm = llm

    def scan_underlying(self, underlying: Underlying, notify: bool = True) -> AnalysisResult | None:
        """对单个标的执行完整的四阶段分析流水线"""
        logger.info(f"{'='*50}")
        logger.info(f"开始分析: {underlying.name}")

        # ── Stage 1: 数据获取 ──
        try:
            chain = self.fetcher.fetch_option_chain(underlying)
            history = self.fetcher.fetch_underlying_history(underlying, days=120)
        except Exception as e:
            logger.error(f"Stage 1 数据获取失败 [{underlying.name}]: {e}")
            return None

        total = len(chain.calls) + len(chain.puts)
        logger.info(f"Stage 1 完成: 获取 {total} 个合约, {len(history)} 条历史数据")

        if total == 0:
            logger.warning(f"未获取到期权合约数据: {underlying.name}")
            return None

        # ── Stage 2: 指标计算 ──
        closes = [h["close"] for h in history if h.get("close")]

        # 计算历史波动率
        vol_data = VolatilityData(
            hv10=calc_historical_volatility(closes, 10),
            hv20=calc_historical_volatility(closes, 20),
            hv60=calc_historical_volatility(closes, 60),
        )

        # ATM IV: 取距离标的价格最近的 call/put 的平均 IV
        atm_iv = self._calc_atm_iv(chain)
        vol_data.iv_atm = atm_iv

        # IV 分位数和 IV Rank (如果有历史 IV 数据，暂时用 HV 序列近似)
        # TODO: 后续接入历史 IV 数据源
        if closes:
            hv_series = [
                calc_historical_volatility(closes[:i], 20)
                for i in range(21, len(closes) + 1)
            ]
            if hv_series and atm_iv > 0:
                vol_data.iv_percentile = calc_iv_percentile(atm_iv, hv_series)
                vol_data.iv_rank = calc_iv_rank(atm_iv, hv_series)

        chain.volatility = vol_data

        # 筛选候选合约
        candidates = screen_candidates(chain)
        logger.info(
            f"Stage 2 完成: HV20={vol_data.hv20}%, IV_ATM={vol_data.iv_atm}%, "
            f"IV分位={vol_data.iv_percentile}, 候选={len(candidates)}"
        )

        # ── Stage 3: LLM 决策 ──
        snapshot = build_market_snapshot(chain, vol_data, candidates, closes)
        snapshot_json = snapshot_to_json(snapshot)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            scan_time=snapshot.scan_time,
            underlying_name=underlying.name,
            market_snapshot_json=snapshot_json,
        )

        logger.info(f"Stage 3: 向 LLM 发送分析请求 (上下文 ~{len(snapshot_json)} 字符)")
        logger.debug(f"[快照JSON]\n{snapshot_json}")
        logger.debug(f"[系统提示词]\n{SYSTEM_PROMPT}")
        logger.debug(f"[用户提示词]\n{user_prompt}")
        try:
            raw_response = self.llm.chat(SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.error(f"Stage 3 LLM 调用失败: {e}")
            return None

        logger.debug(f"[LLM原始返回]\n{raw_response}")
        result = parse_llm_response(raw_response, underlying.name)
        logger.info(
            f"Stage 3 完成: 市场评估={result.market_assessment[:50]}... "
            f"信号数={len(result.signals)}"
        )

        # ── Stage 4: 通知 ──
        if notify:
            message = format_analysis(result)
            send_notify(message)
            logger.info(f"Stage 4 完成: 通知已发送")
        else:
            logger.info(f"Stage 4 跳过: notify=False")

        return result

    def scan_all(self, underlyings: list[Underlying], notify: bool = True) -> list[AnalysisResult]:
        """扫描所有监控标的"""
        results = []
        for u in underlyings:
            try:
                result = self.scan_underlying(u, notify=notify)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"分析 {u.name} 时出错: {e}")
                continue
        return results

    def _calc_atm_iv(self, chain) -> float:
        """计算 ATM 隐含波动率 (取最接近标的价格的合约 IV)"""
        price = chain.underlying.price
        if price <= 0:
            # 如果没有标的价格，取所有有 IV 的合约的中位数
            all_ivs = [c.iv for c in chain.calls + chain.puts if c.iv > 0]
            if all_ivs:
                all_ivs.sort()
                return all_ivs[len(all_ivs) // 2]
            return 0.0

        all_contracts = chain.calls + chain.puts
        if not all_contracts:
            return 0.0

        # 找距离标的价格最近的合约
        near = sorted(
            [c for c in all_contracts if c.iv > 0],
            key=lambda c: abs(c.strike - price),
        )
        if not near:
            return 0.0

        # 取最近 2-4 个合约的平均 IV
        top = near[:4]
        return round(sum(c.iv for c in top) / len(top), 2)
