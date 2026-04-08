"""解析 LLM 输出的 JSON 信号"""

import json
import logging
import re
import uuid
from datetime import datetime

from src.models.signal import AnalysisResult, SignalLeg, TradingSignal

logger = logging.getLogger(__name__)


def parse_llm_response(raw_response: str, underlying_name: str) -> AnalysisResult:
    """解析 LLM 返回的 JSON 文本为结构化信号"""

    # 提取 JSON 部分 (LLM 可能输出额外文本)
    json_str = _extract_json(raw_response)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}\n原始回复: {raw_response[:500]}")
        return AnalysisResult(
            underlying=underlying_name,
            market_assessment="LLM 输出解析失败",
            no_action_reasons=[f"JSON解析错误: {str(e)}"],
            raw_response=raw_response,
        )

    # 解析信号
    signals = []
    for s in data.get("signals", []):
        legs = [
            SignalLeg(
                code=leg.get("code", ""),
                direction=leg.get("direction", ""),
                quantity=int(leg.get("quantity", 1)),
                name=leg.get("name", ""),
            )
            for leg in s.get("legs", [])
        ]

        signal = TradingSignal(
            signal_id=str(uuid.uuid4())[:8],
            underlying=underlying_name,
            action=s.get("action", "unknown"),
            legs=legs,
            rationale=s.get("rationale", ""),
            risk_warning=s.get("risk_warning", ""),
            confidence=s.get("confidence", "medium"),
            urgency=s.get("urgency", "within_session"),
            created_at=datetime.now(),
        )
        signals.append(signal)

    return AnalysisResult(
        underlying=underlying_name,
        market_assessment=data.get("market_assessment", ""),
        signals=signals,
        no_action_reasons=data.get("no_action_reasons", []),
        raw_response=raw_response,
    )


def _extract_json(text: str) -> str:
    """从 LLM 回复中提取 JSON 块"""
    # 尝试匹配 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)

    # 尝试直接找第一个 { ... } 块
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)

    return text
