"""期权合约筛选器 — 从完整期权链中筛选出有意义的候选合约"""

from __future__ import annotations

import logging

from config.strategies import STRATEGY_PARAMS
from src.models.market import OptionChain, OptionContract

logger = logging.getLogger(__name__)

_SCREEN = STRATEGY_PARAMS["screening"]


def screen_candidates(chain: OptionChain) -> list[OptionContract]:
    """筛选候选合约

    过滤规则:
    1. 成交量 >= min_volume
    2. 持仓量 >= min_open_interest
    3. 到期天数 >= min_days_to_expiry
    4. 行权价在 ATM 附近 (moneyness_levels 档)
    """
    all_contracts = chain.calls + chain.puts
    if not all_contracts:
        return []

    underlying_price = chain.underlying.price
    candidates = []

    for c in all_contracts:
        # 基本流动性过滤
        if c.volume < _SCREEN["min_volume"]:
            continue
        # OI 过滤 (某些数据源不返回持仓量, 值为0时跳过此过滤)
        if c.open_interest > 0 and c.open_interest < _SCREEN["min_open_interest"]:
            continue
        # 到期日过滤
        if c.days_to_expiry < _SCREEN["min_days_to_expiry"]:
            continue

        # IV 有效性过滤 (深度实值/虚值的 IV 不可靠)
        if c.iv < 1.0:  # IV < 1% 基本是无效数据
            continue

        # Moneyness 过滤 (行权价在标的价格附近)
        if underlying_price > 0:
            moneyness = abs(c.strike - underlying_price) / underlying_price
            # 允许上下 15% 范围内的合约
            if moneyness > 0.15:
                continue

        candidates.append(c)

    # 按成交量排序，取 top N
    candidates.sort(key=lambda x: x.volume, reverse=True)
    max_n = 15
    result = candidates[:max_n]

    logger.info(
        f"筛选结果: {len(all_contracts)} 个合约 → {len(result)} 个候选 "
        f"(标的价格={underlying_price})"
    )
    return result
