"""上下文构建器 — 将 OptionChain + 计算结果转为喂给 LLM 的 MarketSnapshot JSON"""

from __future__ import annotations

import json
from datetime import datetime

from src.models.market import MarketSnapshot, OptionChain, OptionContract, VolatilityData
from src.compute.technicals import calc_ma, calc_rsi, determine_trend


def build_market_snapshot(
    chain: OptionChain,
    vol_data: VolatilityData,
    candidates: list[OptionContract],
    history_closes: list[float],
) -> MarketSnapshot:
    """构建 LLM 上下文快照"""

    # 标的摘要
    u = chain.underlying
    underlying_info = {
        "code": u.code,
        "name": u.name,
        "price": u.price,
        "change_pct": u.change_pct,
        "volume": u.volume,
    }

    # 如果有历史数据，补充技术指标
    if history_closes:
        underlying_info.update({
            "ma5": calc_ma(history_closes, 5),
            "ma20": calc_ma(history_closes, 20),
            "ma60": calc_ma(history_closes, 60),
            "rsi14": calc_rsi(history_closes, 14),
            "trend": determine_trend(history_closes),
        })

    # 波动率摘要
    vol_info = {
        "hv10": vol_data.hv10,
        "hv20": vol_data.hv20,
        "hv60": vol_data.hv60,
        "iv_atm": vol_data.iv_atm,
        "iv_percentile": vol_data.iv_percentile,
        "iv_rank": vol_data.iv_rank,
    }

    # 判断 IV 相对 HV 的关系
    if vol_data.iv_atm > 0 and vol_data.hv20 > 0:
        spread = vol_data.iv_atm - vol_data.hv20
        if spread > 5:
            vol_info["iv_vs_hv"] = f"iv_premium(+{spread:.1f})"
        elif spread < -5:
            vol_info["iv_vs_hv"] = f"iv_discount({spread:.1f})"
        else:
            vol_info["iv_vs_hv"] = "neutral"

    # 候选合约摘要
    candidate_list = []
    for c in candidates:
        candidate_list.append({
            "code": c.code,
            "name": c.name,
            "type": c.option_type,
            "strike": c.strike,
            "expiry": c.expiry,
            "days_to_expiry": c.days_to_expiry,
            "last_price": c.last_price,
            "iv": c.iv,
            "volume": c.volume,
            "open_interest": c.open_interest,
            "greeks": {
                "delta": c.greeks.delta,
                "gamma": c.greeks.gamma,
                "theta": c.greeks.theta,
                "vega": c.greeks.vega,
            },
        })

    return MarketSnapshot(
        scan_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        underlying=underlying_info,
        volatility=vol_info,
        candidates=candidate_list,
    )


def snapshot_to_json(snapshot: MarketSnapshot) -> str:
    """将 MarketSnapshot 序列化为 JSON 字符串"""
    data = {
        "scan_time": snapshot.scan_time,
        "underlying": snapshot.underlying,
        "volatility": snapshot.volatility,
        "candidates": snapshot.candidates,
    }
    if snapshot.market_context:
        data["market_context"] = snapshot.market_context
    return json.dumps(data, ensure_ascii=False, indent=2)
