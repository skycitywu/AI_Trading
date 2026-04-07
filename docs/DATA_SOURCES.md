# 数据源调研报告

> 调研日期：2026-04-07
> 运行环境：macOS Python 3.9，LibreSSL（非 OpenSSL）

## 结论速览

| 数据源 | ETF期权 | 商品期权 | 状态 |
|--------|---------|---------|------|
| AKShare + Sina | ✅ 合约/Greeks/IV | — | **主力，稳定** |
| AKShare + SSE官方 | ✅ 合约列表 | — | 稳定 |
| AKShare + 东方财富 | ⚠️ 偶发断连 | ⚠️ 偶发断连 | 不稳定 |
| AKShare + CZCE | — | ✅ 含Delta+IV | 稳定 |
| AKShare + SHFE | — | ✅ 含Delta，无IV | 稳定 |
| AKShare + DCE | — | ❌ JSON decode error | 当前不可用 |
| 博弈大师 PoboAPI | 平台内SDK | 平台内SDK | 不可独立调用 |

---

## ETF 期权（50ETF / 300ETF）

### 可用接口

#### 合约基本信息
```python
ak.option_current_day_sse()
# 返回列: 合约编码, 合约交易代码, 合约简称, 标的券名称及代码,
#         类型(认购/认沽), 行权价, 合约单位, 期权行权日, 到期日, 开始日期
# 特点: SSE官方数据，稳定，包含所有在上市合约（约600条）
```

#### Greeks + 隐含波动率（逐合约）
```python
ak.option_sse_greeks_sina(symbol="10011105")
# 返回: key-value DataFrame（13行）
# 字段: 期权合约简称, 成交量, Delta, Gamma, Theta, Vega, 隐含波动率,
#       最高价, 最低价, 交易代码, 行权价, 最新价, 理论价值
# ⚠️ IV 是小数形式（0.1521 = 15.21%），需 *100 转为百分比
# ⚠️ 不含持仓量 (open_interest=0)
# ⚠️ 每次只能查一个合约，需逐个调用（加 sleep 0.15s 防限流）
```

#### 实时行情（逐合约，更详细）
```python
ak.option_sse_spot_price_sina(symbol="10011105")
# 返回: key-value DataFrame（43行）
# 字段: 买量/卖量/最新价/持仓量/涨幅/昨收/开盘/成交量/成交额/五档盘口 等
```

#### 标的 ETF 历史日线
```python
ak.fund_etf_hist_em(symbol="510050", period="daily",
                    start_date="20260101", end_date="20260407", adjust="")
# 返回列: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
# ⚠️ 使用东方财富接口，偶发连接断开
```

#### 到期月份列表
```python
ak.option_sse_list_sina(symbol="50ETF", exchange="null")
# 返回: ['202604', '202605', '202606', '202609']
```

#### QVIX（中国波动率指数）
```python
ak.index_option_50etf_qvix()   # 50ETF QVIX 日线
ak.index_option_300etf_qvix()  # 300ETF QVIX 日线
# 返回列: date, open, high, low, close
```

### 当前不可用接口
```python
ak.option_current_em()         # 东方财富 — 连接被断
ak.option_risk_analysis_em()   # 东方财富 — 连接被断
ak.option_value_analysis_em()  # 东方财富 — 连接被断
ak.option_risk_indicator_sse(date="20260407")  # 列名与文档不符（API变更）
```

---

## 商品期货期权

### CZCE 郑商所（白糖、棉花、菜粕等）✅

```python
ak.option_hist_czce(symbol="白糖期权", trade_date="20260403")
# 返回列: 合约代码, 昨结算, 今开盘, 最高价, 最低价, 今收盘, 今结算,
#         涨跌1, 涨跌2, 成交量(手), 持仓量, 增减量, 成交额(万元),
#         DELTA, 隐含波动率, 行权量
# ✅ 含 Delta + 隐含波动率（百分比形式，如 44.96 表示44.96%）
# 支持品种: 白糖/棉花/甲醇/PTA/动力煤/菜籽粕/菜籽油/花生/对二甲苯等
```

### SHFE 上期所（铜、铝、锌、螺纹钢等）✅

```python
ak.option_hist_shfe(symbol="铜期权", trade_date="20260403")
# 返回列: 合约代码, 开盘价, 最高价, 最低价, 收盘价, 前结算价, 结算价,
#         涨跌1, 涨跌2, 成交量, 持仓量, 持仓量变化, 成交额, 德尔塔, 行权量
# ✅ 含德尔塔(Delta)
# ❌ 无隐含波动率（需用 option_vol_shfe 单独查）
# 支持品种: 铜/铝/锌/铅/螺纹钢/镍/锡/氧化铝/黄金/白银等
```

#### SHFE 隐含波动率（单独接口）
```python
ak.option_vol_shfe(symbol="铜期权", trade_date="20260403")
# 返回列: 合约系列, 成交量, 持仓量, 持仓量变化, 成交额, 行权量, 隐含波动率
```

### DCE 大商所（豆粕、玉米、铁矿石等）❌ 当前不可用

```python
ak.option_hist_dce(symbol="豆粕期权", trade_date="20260407")
# 错误: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
# 已尝试过去5天的日期，均失败
# 后续可重新测试，或联系 AKShare 社区排查
```

---

## 博弈大师（真格量化）PoboAPI

### 结论：不可独立调用

PoboAPI 是**事件驱动平台内 SDK**，策略代码必须运行在真格量化平台上：

```python
from PoboAPI import *  # 只能在平台内运行

def OnStart(context):
    context.accounts["回测期货"].Login()

def OnBar(context, bar):
    delta = GetOptionDeltaByCode("m2409-C-3300.DCE")  # 平台内函数
    iv = GetVolatilityByCode("m2409.DCE")
```

无法 `pip install PoboAPI`，无法从外部通过 HTTP 调用。

### Pobo 提供的期权 API（平台内可用）

| 函数 | 说明 |
|------|------|
| `GetOptionDeltaByCode(code)` | 计算 Delta |
| `GetOptionGammaByCode(code)` | 计算 Gamma |
| `GetOptionThetaByCode(code)` | 计算 Theta |
| `GetOptionVegaByCode(code)` | 计算 Vega |
| `GetOptionRhoByCode(code)` | 计算 Rho |
| `GetVolatilityByCode(code)` | 计算历史波动率 |
| `GetOptionBSPriceByCode(code)` | BS模型理论价格 |
| `GetAtmOptionContractByPos(code, expiry, strike, type)` | 按档位获取期权合约 |
| `GetQuote(code)` | 实时行情 |
| `GetHisData2(code, BarType.Day)` | 历史K线 |

### 后续桥接方案（Phase 3 探索）

在 Pobo 平台内运行一个"数据导出策略"：
1. 在 `OnBar()` 或 `OnMarketQuotationInitialEx()` 中调用 Pobo 函数获取数据
2. 通过 `import requests` 将数据 POST 到本地 HTTP 服务，或写入共享文件
3. 本地 AI Agent 从文件/HTTP 读取数据

**需要验证**：Pobo 平台内是否允许 `import requests` 或写文件操作。

---

## 数据字段注意事项

### IV 单位统一
不同数据源 IV 格式不同，已在 fetcher 中统一转为 **百分比形式（如 18.5 表示 18.5%）**：

| 数据源 | 原始格式 | 转换 |
|--------|---------|------|
| Sina Greeks | 小数（0.1521） | × 100 → 15.21% |
| CZCE 日数据 | 百分比（44.96） | 直接使用 |
| SHFE vol | 百分比 | 直接使用 |

### 合约代码格式

| 市场 | 示例 | 解析规则 |
|------|------|---------|
| SSE ETF期权 | `10011105` | 数字编码，需查表 |
| ETF期权交易代码 | `510050C2604M02950` | 标的+类型+年月+行权价 |
| CZCE商品期权 | `SR605C4600` | 品种+到期月+类型+行权价 |
| SHFE商品期权 | `cu2605C70000` | 品种+到期月+类型+行权价 |
| DCE商品期权 | `m2409-C-3300` | 品种-类型-行权价 |
