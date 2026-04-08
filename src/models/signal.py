"""交易信号模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SignalLeg:
    """信号的单腿"""
    code: str                # 合约代码
    direction: str           # "buy" or "sell"
    quantity: int = 1
    name: str = ""           # 合约名称，如"50ETF沽4月3000"


@dataclass
class TradingSignal:
    """一条交易信号"""
    signal_id: str                          # 唯一ID
    underlying: str                         # 标的名称
    action: str                             # 策略类型: sell_strangle, buy_straddle, etc.
    legs: list[SignalLeg] = field(default_factory=list)
    rationale: str = ""                     # LLM生成的交易理由
    risk_warning: str = ""                  # 风险提示
    confidence: str = "medium"              # high / medium / low
    urgency: str = "within_session"         # immediate / within_session / next_session
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AnalysisResult:
    """LLM 分析结果"""
    underlying: str
    market_assessment: str                  # 市场整体判断
    signals: list[TradingSignal] = field(default_factory=list)
    no_action_reasons: list[str] = field(default_factory=list)
    raw_response: str = ""                  # LLM原始返回
    created_at: datetime = field(default_factory=datetime.now)
