"""技术指标计算"""

from __future__ import annotations

import numpy as np


def calc_ma(closes: list[float], period: int) -> float:
    """简单移动平均线"""
    if len(closes) < period:
        return 0.0
    return round(float(np.mean(closes[-period:])), 4)


def calc_rsi(closes: list[float], period: int = 14) -> float:
    """RSI 相对强弱指标"""
    if len(closes) < period + 1:
        return 50.0

    prices = closes[-(period + 1):]
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    gains = [c for c in changes if c > 0]
    losses = [-c for c in changes if c < 0]

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def determine_trend(closes: list[float]) -> str:
    """判断趋势方向"""
    if len(closes) < 20:
        return "unknown"

    ma5 = calc_ma(closes, 5)
    ma20 = calc_ma(closes, 20)
    current = closes[-1]

    if current > ma5 > ma20:
        return "bullish"
    elif current < ma5 < ma20:
        return "bearish"
    elif current > ma20:
        return "neutral_bullish"
    else:
        return "neutral_bearish"
