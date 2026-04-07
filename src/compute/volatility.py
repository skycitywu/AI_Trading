"""波动率计算"""

from __future__ import annotations

import math
import numpy as np


def calc_historical_volatility(closes: list[float], window: int) -> float:
    """计算历史波动率 (年化)

    Args:
        closes: 收盘价序列 (至少 window+1 个数据点)
        window: 计算窗口 (10, 20, 60)
    Returns:
        年化历史波动率 (百分比, e.g. 22.5 表示 22.5%)
    """
    if len(closes) < window + 1:
        return 0.0

    prices = closes[-(window + 1):]
    log_returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
    std = float(np.std(log_returns, ddof=1))
    # 年化: 期货约 242 个交易日
    annualized = std * math.sqrt(242) * 100
    return round(annualized, 2)


def calc_iv_percentile(current_iv: float, historical_ivs: list[float]) -> float:
    """计算 IV 分位数 (过去一年中，有多少比例的天数 IV 低于当前值)

    Returns:
        0-100 的分位数
    """
    if not historical_ivs or current_iv <= 0:
        return 50.0  # 无数据时返回中性值

    below = sum(1 for iv in historical_ivs if iv < current_iv)
    return round(below / len(historical_ivs) * 100, 1)


def calc_iv_rank(current_iv: float, historical_ivs: list[float]) -> float:
    """计算 IV Rank = (当前IV - 最低IV) / (最高IV - 最低IV) * 100

    Returns:
        0-100 的排名值
    """
    if not historical_ivs:
        return 50.0

    iv_min = min(historical_ivs)
    iv_max = max(historical_ivs)
    if iv_max == iv_min:
        return 50.0

    return round((current_iv - iv_min) / (iv_max - iv_min) * 100, 1)
