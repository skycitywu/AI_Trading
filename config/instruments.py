"""监控标的配置 - ETF期权 + 商品期货期权"""

from dataclasses import dataclass


@dataclass
class Underlying:
    code: str           # 标的代码
    name: str           # 中文名
    market: str         # "etf_option" or "commodity_option"
    exchange: str       # 交易所


# MVP 监控标的列表
WATCHED_UNDERLYINGS = [
    # ETF 期权 (SSE Sina 接口)
    Underlying("510050", "50ETF", "etf_option", "SSE"),
    Underlying("510300", "300ETF", "etf_option", "SSE"),
    # 商品期货期权 (交易所日数据)
    # DCE 豆粕暂不可用 (接口返回空)
    Underlying("白糖", "白糖期权", "commodity_option", "CZCE"),
    Underlying("铜", "铜期权", "commodity_option", "SHFE"),
]
