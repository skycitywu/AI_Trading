"""信号格式化 — 将结构化信号转为人类可读消息"""

from src.models.signal import AnalysisResult, TradingSignal

CONFIDENCE_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
DIRECTION_MAP = {"buy": "买入", "sell": "卖出"}


def format_analysis(result: AnalysisResult) -> str:
    """将分析结果格式化为微信消息文本"""
    lines = []
    lines.append(f"📊 【{result.underlying}】期权分析报告")
    lines.append(f"⏰ {result.created_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 市场评估
    if result.market_assessment:
        lines.append(f"📈 市场评估:")
        lines.append(result.market_assessment)
        lines.append("")

    # 交易信号
    if result.signals:
        lines.append(f"🎯 发现 {len(result.signals)} 个交易信号:")
        lines.append("")
        for i, sig in enumerate(result.signals, 1):
            lines.append(_format_signal(i, sig))
            lines.append("")
    else:
        lines.append("✅ 当前无推荐交易信号")
        if result.no_action_reasons:
            for reason in result.no_action_reasons:
                lines.append(f"  - {reason}")

    return "\n".join(lines)


def _format_signal(index: int, sig: TradingSignal) -> str:
    """格式化单条信号"""
    emoji = CONFIDENCE_EMOJI.get(sig.confidence, "⚪")
    lines = []
    lines.append(f"{'─' * 30}")
    lines.append(f"{emoji} 信号#{index}: {sig.action}")
    lines.append(f"信心: {sig.confidence} | 紧急度: {sig.urgency}")

    if sig.legs:
        lines.append("操作:")
        for leg in sig.legs:
            d = DIRECTION_MAP.get(leg.direction, leg.direction)
            lines.append(f"  {d} {leg.code} x{leg.quantity}")

    if sig.rationale:
        lines.append(f"理由: {sig.rationale}")
    if sig.risk_warning:
        lines.append(f"⚠️ 风险: {sig.risk_warning}")

    return "\n".join(lines)
