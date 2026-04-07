"""策略参数配置"""


STRATEGY_PARAMS = {
    "sell_high_iv": {
        "iv_percentile_threshold": 70,   # IV分位数 > 70 触发
        "iv_hv_spread_min": 5.0,         # IV - HV > 5% 才考虑卖
        "min_days_to_expiry": 14,        # 至少14天到期
        "max_days_to_expiry": 60,        # 最多60天到期
    },
    "buy_low_iv": {
        "iv_percentile_threshold": 30,   # IV分位数 < 30 触发
        "min_days_to_expiry": 20,
        "max_days_to_expiry": 90,
    },
    "directional": {
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "trend_ma_period": 20,
    },
    "screening": {
        "min_volume": 500,               # 最低成交量
        "min_open_interest": 1000,       # 最低持仓量
        "min_days_to_expiry": 7,         # 过滤临近到期合约
        "max_moneyness_levels": 3,       # ATM上下各3档
    },
}
