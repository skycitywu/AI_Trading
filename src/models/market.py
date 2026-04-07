"""市场数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Quote:
    """标的行情"""
    code: str
    name: str
    price: float
    change_pct: float       # 涨跌幅 %
    open: float
    high: float
    low: float
    pre_close: float
    volume: float           # 成交量
    amount: float           # 成交额
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Greeks:
    """期权希腊字母"""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0


@dataclass
class OptionContract:
    """单个期权合约"""
    code: str               # 合约代码
    name: str               # 合约名称
    underlying_code: str    # 标的代码
    option_type: str        # "call" or "put"
    strike: float           # 行权价
    expiry: str             # 到期日 YYYY-MM-DD
    days_to_expiry: int     # 距到期天数
    last_price: float       # 最新价
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0         # 成交量
    open_interest: int = 0  # 持仓量
    iv: float = 0.0         # 隐含波动率 %
    greeks: Greeks = field(default_factory=Greeks)


@dataclass
class VolatilityData:
    """波动率数据"""
    hv10: float = 0.0       # 10日历史波动率
    hv20: float = 0.0       # 20日历史波动率
    hv60: float = 0.0       # 60日历史波动率
    iv_atm: float = 0.0     # ATM隐含波动率
    iv_percentile: float = 0.0   # IV年度分位数 (0-100)
    iv_rank: float = 0.0         # IV Rank (0-100)


@dataclass
class OptionChain:
    """期权链"""
    underlying: Quote
    volatility: VolatilityData
    calls: list[OptionContract] = field(default_factory=list)
    puts: list[OptionContract] = field(default_factory=list)
    scan_time: datetime = field(default_factory=datetime.now)


@dataclass
class MarketSnapshot:
    """喂给 LLM 的市场快照 (Stage 2 → Stage 3 的数据结构)"""
    scan_time: str
    underlying: dict        # 标的摘要信息
    volatility: dict        # 波动率分析
    candidates: list[dict]  # 筛选后的候选合约
    market_context: Optional[str] = None
