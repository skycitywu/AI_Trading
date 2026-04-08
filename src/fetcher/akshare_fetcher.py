"""AKShare 数据获取实现

数据源策略 (根据实际可用性选择):
- ETF 期权: SSE官方合约列表 + Sina Greeks/行情 (逐个合约)
- 商品期权: CZCE/SHFE 交易所日数据 (批量，含Delta+IV)
- ETF 历史: 东方财富 fund_etf_hist_em
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from config.instruments import Underlying
from src.fetcher.base import BaseFetcher
from src.models.market import (
    Greeks, OptionChain, OptionContract, Quote, VolatilityData,
)

logger = logging.getLogger(__name__)


class AKShareFetcher(BaseFetcher):

    # ── ETF 期权 ──────────────────────────────────────────────

    def _fetch_etf_option_chain(self, underlying: Underlying) -> OptionChain:
        """获取 ETF 期权链

        步骤:
        1. option_current_day_sse() 获取全部合约基本信息
        2. 过滤出目标标的 + 近月合约
        3. option_sse_greeks_sina() 逐个获取 Greeks/IV/价格
        """
        quote = self._fetch_etf_quote(underlying)

        # 1) 获取所有 SSE 在上市合约
        try:
            df_contracts = ak.option_current_day_sse()
        except Exception as e:
            logger.error(f"获取SSE合约列表失败: {e}")
            return OptionChain(underlying=quote, volatility=VolatilityData())

        # 2) 过滤目标标的
        target_code = underlying.code
        df_filtered = df_contracts[
            df_contracts["标的券名称及代码"].str.contains(target_code, na=False)
        ].copy()

        if df_filtered.empty:
            logger.warning(f"未找到 {target_code} 相关期权合约")
            return OptionChain(underlying=quote, volatility=VolatilityData())

        # 3) 解析到期日，只保留最近2个月份
        df_filtered["到期日_dt"] = pd.to_datetime(df_filtered["到期日"], format="%Y%m%d")
        expiry_months = sorted(df_filtered["到期日_dt"].unique())
        keep_months = expiry_months[:2]  # 近月 + 次近月
        df_filtered = df_filtered[df_filtered["到期日_dt"].isin(keep_months)]

        # 4) 行权价过滤: 只保留 ATM 附近的合约 (标的价格 ±15%)
        if quote.price > 0:
            low = quote.price * 0.85
            high = quote.price * 1.15
            df_filtered = df_filtered[
                (df_filtered["行权价"].astype(float) >= low) &
                (df_filtered["行权价"].astype(float) <= high)
            ]

        logger.info(f"ETF期权: 过滤后 {len(df_filtered)} 个合约, 开始逐个获取Greeks...")

        # 5) 逐个获取 Greeks
        calls, puts = [], []
        now = datetime.now()

        for _, row in df_filtered.iterrows():
            contract_code = str(row["合约编码"])
            try:
                greeks_df = ak.option_sse_greeks_sina(symbol=contract_code)
                greeks_dict = dict(zip(greeks_df["字段"], greeks_df["值"]))
                time.sleep(0.15)  # 避免被限流
            except Exception as e:
                logger.debug(f"获取Greeks失败 {contract_code}: {e}")
                continue

            expiry_date = row["到期日_dt"]
            dte = (expiry_date - pd.Timestamp(now)).days
            is_call = str(row["类型"]) == "认购"

            contract = OptionContract(
                code=contract_code,
                name=str(row["合约简称"]),
                underlying_code=target_code,
                option_type="call" if is_call else "put",
                strike=float(row["行权价"]),
                expiry=expiry_date.strftime("%Y-%m-%d"),
                days_to_expiry=max(dte, 0),
                last_price=float(greeks_dict.get("最新价", 0) or 0),
                volume=int(float(greeks_dict.get("成交量", 0) or 0)),
                open_interest=0,  # Sina Greeks 接口不含持仓量
                iv=float(greeks_dict.get("隐含波动率", 0) or 0) * 100,  # Sina返回小数,转为百分比
                greeks=Greeks(
                    delta=float(greeks_dict.get("Delta", 0) or 0),
                    gamma=float(greeks_dict.get("Gamma", 0) or 0),
                    theta=float(greeks_dict.get("Theta", 0) or 0),
                    vega=float(greeks_dict.get("Vega", 0) or 0),
                ),
            )
            (calls if is_call else puts).append(contract)

        logger.info(f"ETF期权获取完成: calls={len(calls)}, puts={len(puts)}")

        # 兜底: 若行情接口全部失败，从 ATM call (Delta≈0.5) 的行权价估算标的价格
        if quote.price == 0 and calls:
            atm_call = min(calls, key=lambda c: abs(c.greeks.delta - 0.5))
            estimated_price = atm_call.strike
            logger.warning(f"标的价格获取失败，用ATM行权价估算: {estimated_price}")
            quote = Quote(
                code=quote.code, name=quote.name,
                price=estimated_price, change_pct=0,
                open=estimated_price, high=estimated_price, low=estimated_price,
                pre_close=estimated_price, volume=0, amount=0,
            )

        return OptionChain(
            underlying=quote,
            volatility=VolatilityData(),
            calls=calls,
            puts=puts,
            scan_time=now,
        )

    def _fetch_etf_quote(self, underlying: Underlying) -> Quote:
        """获取 ETF 最新行情，优先东方财富，失败则用 stock_zh_a_hist 备用"""
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")

        for fetch_fn, kwargs, col in [
            (ak.fund_etf_hist_em, dict(
                symbol=underlying.code, period="daily",
                start_date=start, end_date=end, adjust="",
            ), {"close": "收盘", "change_pct": "涨跌幅", "open": "开盘", "high": "最高",
                "low": "最低", "pre_close": "昨收", "volume": "成交量", "amount": "成交额"}),
            (ak.stock_zh_a_hist, dict(
                symbol=underlying.code, period="daily",
                start_date=start, end_date=end, adjust="",
            ), {"close": "收盘", "change_pct": "涨跌幅", "open": "开盘", "high": "最高",
                "low": "最低", "pre_close": "昨收", "volume": "成交量", "amount": "成交额"}),
            (ak.fund_etf_hist_sina, dict(
                symbol=f"sh{underlying.code}",
            ), {"close": "close", "change_pct": None, "open": "open", "high": "high",
                "low": "low", "pre_close": "prevclose", "volume": "volume", "amount": "amount"}),
        ]:
            try:
                df = fetch_fn(**kwargs)
                if df is None or df.empty:
                    continue
                row = df.iloc[-1]
                pre_close_col = col["pre_close"]
                pre_close = float(row[pre_close_col]) if pre_close_col and pre_close_col in row.index else float(row[col["open"]])
                return Quote(
                    code=underlying.code,
                    name=underlying.name,
                    price=float(row[col["close"]]),
                    change_pct=float(row[col["change_pct"]]) if col["change_pct"] and col["change_pct"] in row.index else 0,
                    open=float(row[col["open"]]),
                    high=float(row[col["high"]]),
                    low=float(row[col["low"]]),
                    pre_close=pre_close,
                    volume=float(row[col["volume"]]),
                    amount=float(row[col["amount"]]) if col["amount"] and col["amount"] in row.index else 0,
                )
            except Exception as e:
                logger.warning(f"获取ETF行情失败 [{fetch_fn.__name__}] {underlying.code}: {e}")

        return Quote(
            code=underlying.code, name=underlying.name,
            price=0, change_pct=0, open=0, high=0, low=0,
            pre_close=0, volume=0, amount=0,
        )

    def _fetch_etf_history(self, underlying: Underlying, days: int) -> list[dict]:
        """获取 ETF 历史日线，优先东方财富，失败则用 stock_zh_a_hist 备用"""
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        # 三个备用接口: 东方财富 → stock_zh_a_hist → 网易163
        sources = [
            (ak.fund_etf_hist_em, dict(
                symbol=underlying.code, period="daily",
                start_date=start, end_date=end, adjust="",
            ), {"日期": "日期", "收盘": "收盘", "最高": "最高", "最低": "最低", "成交量": "成交量"}),
            (ak.stock_zh_a_hist, dict(
                symbol=underlying.code, period="daily",
                start_date=start, end_date=end, adjust="",
            ), {"日期": "日期", "收盘": "收盘", "最高": "最高", "最低": "最低", "成交量": "成交量"}),
            (ak.fund_etf_hist_sina, dict(
                symbol=f"sh{underlying.code}",
            ), {"日期": "date", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"}),
        ]

        for fetch_fn, kwargs, col_map in sources:
            try:
                df = fetch_fn(**kwargs)
                if df is None or df.empty:
                    continue
                # 过滤日期范围（163接口不支持传入日期参数）
                if "日期" in df.columns:
                    df = df[df["日期"] >= start]
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "date": str(row[col_map["日期"]]),
                        "close": float(row[col_map["收盘"]]),
                        "high": float(row[col_map["最高"]]),
                        "low": float(row[col_map["最低"]]),
                        "volume": float(row[col_map["成交量"]]),
                    })
                logger.info(f"ETF历史数据获取成功 [{fetch_fn.__name__}]: {len(records)} 条")
                return records[-days:]
            except Exception as e:
                logger.error(f"获取ETF历史数据失败 [{fetch_fn.__name__}]: {e}")

        return []

    # ── 商品期货期权 ──────────────────────────────────────────

    def _fetch_commodity_option_chain(self, underlying: Underlying) -> OptionChain:
        """获取商品期货期权链 (CZCE/SHFE 交易所日数据，含 Delta + IV)"""
        quote = Quote(
            code=underlying.code, name=underlying.name,
            price=0, change_pct=0, open=0, high=0, low=0,
            pre_close=0, volume=0, amount=0,
        )

        exchange = underlying.exchange
        symbol = underlying.code + "期权"

        # 尝试今天和最近几个交易日
        fetch_fn = {
            "CZCE": ak.option_hist_czce,
            "SHFE": ak.option_hist_shfe,
        }.get(exchange)

        if not fetch_fn:
            logger.error(f"不支持的交易所: {exchange} (DCE暂不可用)")
            return OptionChain(underlying=quote, volatility=VolatilityData())

        df = None
        for days_back in range(0, 5):
            date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
            try:
                df = fetch_fn(symbol=symbol, trade_date=date)
                if df is not None and not df.empty:
                    logger.info(f"获取{symbol}数据成功 (日期={date})")
                    break
            except Exception:
                continue

        if df is None or df.empty:
            logger.error(f"获取{symbol}数据失败: 最近5天均无数据")
            return OptionChain(underlying=quote, volatility=VolatilityData())

        calls, puts = [], []
        now = datetime.now()

        # 列名映射 (不同交易所列名不同)
        col_map = self._commodity_col_map(exchange)

        for _, row in df.iterrows():
            try:
                contract_code = str(row[col_map["code"]])
                if not contract_code:
                    continue

                is_call = "C" in contract_code.upper()
                delta_val = float(row.get(col_map["delta"], 0) or 0)
                iv_val = float(row.get(col_map["iv"], 0) or 0)
                close_price = float(row.get(col_map["close"], 0) or 0)
                volume = int(float(row.get(col_map["volume"], 0) or 0))
                oi = int(float(row.get(col_map["oi"], 0) or 0))

                contract = OptionContract(
                    code=contract_code,
                    name=contract_code,
                    underlying_code=underlying.code,
                    option_type="call" if is_call else "put",
                    strike=self._parse_strike_from_code(contract_code),
                    expiry="",
                    days_to_expiry=0,
                    last_price=close_price,
                    volume=volume,
                    open_interest=oi,
                    iv=iv_val,
                    greeks=Greeks(delta=delta_val),
                )
                (calls if is_call else puts).append(contract)
            except Exception as e:
                logger.debug(f"跳过商品期权行: {e}")
                continue

        logger.info(f"{symbol}获取完成: calls={len(calls)}, puts={len(puts)}")

        return OptionChain(
            underlying=quote,
            volatility=VolatilityData(),
            calls=calls,
            puts=puts,
            scan_time=now,
        )

    def _commodity_col_map(self, exchange: str) -> dict:
        """不同交易所的列名映射"""
        if exchange == "CZCE":
            return {
                "code": "合约代码", "delta": "DELTA", "iv": "隐含波动率",
                "close": "今收盘", "volume": "成交量(手)", "oi": "持仓量",
            }
        elif exchange == "SHFE":
            return {
                "code": "合约代码", "delta": "德尔塔", "iv": "隐含波动率",
                "close": "收盘价", "volume": "成交量", "oi": "持仓量",
            }
        return {
            "code": "合约", "delta": "Delta", "iv": "隐含波动率(%)",
            "close": "收盘价", "volume": "成交量", "oi": "持仓量",
        }

    def _parse_strike_from_code(self, code: str) -> float:
        """从合约代码解析行权价

        Examples:
            SR605C4600 -> 4600.0
            cu2605C70000 -> 70000.0
            m2409-C-3300 -> 3300.0
        """
        import re
        # 匹配 C 或 P 后面的数字
        match = re.search(r'[CP](\d+)', code, re.IGNORECASE)
        if match:
            return float(match.group(1))
        # 备选: 取最后的数字段
        nums = re.findall(r'\d+', code)
        if nums:
            return float(nums[-1])
        return 0.0

    def _fetch_commodity_history(self, underlying: Underlying, days: int) -> list[dict]:
        """获取商品期货主力合约历史日线"""
        try:
            symbol_map = {"白糖": "SR0", "铜": "CU0"}
            sina_symbol = symbol_map.get(underlying.code, "")
            if not sina_symbol:
                return []

            df = ak.futures_main_sina(
                symbol=sina_symbol,
                start_date="19900101",
                end_date="22220101",
            )
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": str(row.get("日期", row.get("date", ""))),
                    "close": float(row.get("收盘价", row.get("close", 0))),
                    "high": float(row.get("最高价", row.get("high", 0))),
                    "low": float(row.get("最低价", row.get("low", 0))),
                    "volume": float(row.get("成交量", row.get("volume", 0))),
                })
            return records[-days:]
        except Exception as e:
            logger.error(f"获取商品期货历史数据失败: {e}")
            return []

    # ── 统一接口 ──────────────────────────────────────────────

    def fetch_option_chain(self, underlying: Underlying) -> OptionChain:
        logger.info(f"获取期权链: {underlying.name} ({underlying.market})")
        if underlying.market == "etf_option":
            return self._fetch_etf_option_chain(underlying)
        elif underlying.market == "commodity_option":
            return self._fetch_commodity_option_chain(underlying)
        else:
            raise ValueError(f"不支持的市场类型: {underlying.market}")

    def fetch_underlying_history(self, underlying: Underlying, days: int = 120) -> list[dict]:
        if underlying.market == "etf_option":
            return self._fetch_etf_history(underlying, days)
        elif underlying.market == "commodity_option":
            return self._fetch_commodity_history(underlying, days)
        else:
            return []
