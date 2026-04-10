"""信号格式化 — 将结构化信号转为人类可读消息"""

from __future__ import annotations

from src.models.signal import AnalysisResult, TradingSignal

CONFIDENCE_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
DIRECTION_MAP = {"buy": "买入", "sell": "卖出"}
URGENCY_MAP = {"immediate": "立即", "within_session": "当日内", "next_session": "下一交易日"}


def format_analysis(result: AnalysisResult) -> str:
    """将单个标的的分析结果格式化为消息文本"""
    lines = []
    lines.append(f"📊 【{result.underlying}】")
    lines.append(f"📈 {result.market_assessment}" if result.market_assessment else "")

    if result.signals:
        lines.append(f"🎯 {len(result.signals)} 个信号:")
        for i, sig in enumerate(result.signals, 1):
            lines.append(_format_signal(i, sig))
    else:
        lines.append("✅ 无推荐信号")
        if result.no_action_reasons:
            for reason in result.no_action_reasons:
                lines.append(f"  - {reason}")

    return "\n".join(lines)


def format_scan_round(results: list[AnalysisResult]) -> str:
    """将一轮扫描的所有结果合并为一条消息"""
    if not results:
        return ""

    ts = results[0].created_at.strftime("%Y-%m-%d %H:%M")
    total_signals = sum(len(r.signals) for r in results)

    lines = []
    lines.append(f"📋 AI Trading 扫描报告")
    lines.append(f"⏰ {ts} | {len(results)} 个标的 | {total_signals} 个信号")
    lines.append("")

    for result in results:
        lines.append(format_analysis(result))
        lines.append("")

    return "\n".join(lines)


def _format_signal(index: int, sig: TradingSignal) -> str:
    """格式化单条信号"""
    emoji = CONFIDENCE_EMOJI.get(sig.confidence, "⚪")
    lines = []
    lines.append(f"{'─' * 30}")
    lines.append(f"{emoji} 信号#{index}: {sig.action}")
    urgency_zh = URGENCY_MAP.get(sig.urgency, sig.urgency)
    lines.append(f"信心: {sig.confidence} | 紧急度: {urgency_zh}")

    if sig.legs:
        lines.append("操作:")
        for leg in sig.legs:
            d = DIRECTION_MAP.get(leg.direction, leg.direction)
            label = leg.name if leg.name else leg.code
            lines.append(f"  {d} {label} x{leg.quantity}")

    if sig.rationale:
        lines.append(f"理由: {sig.rationale}")
    if sig.risk_warning:
        lines.append(f"⚠️ 风险: {sig.risk_warning}")

    return "\n".join(lines)
