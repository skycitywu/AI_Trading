"""数据源抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from src.models.market import OptionChain
from config.instruments import Underlying


class BaseFetcher(ABC):
    """数据获取器抽象基类"""

    @abstractmethod
    def fetch_option_chain(self, underlying: Underlying) -> OptionChain:
        """获取完整期权链（含标的行情、Greeks、IV）"""
        ...

    @abstractmethod
    def fetch_underlying_history(self, underlying: Underlying, days: int = 120) -> list[dict]:
        """获取标的历史日线数据，用于计算HV"""
        ...
