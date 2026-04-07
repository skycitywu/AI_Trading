# 系统架构设计

## 设计理念

**确定性代码处理数据，LLM 做分析决策。**

LLM 的短板是处理大量结构化数据（上下文窗口有限、容易遗漏、幻觉）；优势是模式识别、多维度综合判断和生成自然语言推理。因此：

- **Python 代码**：负责 API 调用、数据清洗、Greeks/HV/IV 计算、候选筛选
- **Claude/GLM**：只接收精炼后的结构化摘要，输出交易信号和分析理由

## 整体架构

```
┌──────────────────────────────────────────────────┐
│              SCHEDULER (APScheduler)              │
│  盘前分析(09:00) │ 盘中30min轮询 │ 盘后总结(15:15)│
└──────┬──────────────┬──────────────┬──────────────┘
       ▼              ▼              ▼
┌──────────────────────────────────────────────────┐
│              PIPELINE ORCHESTRATOR                │
│              src/pipeline/orchestrator.py         │
└──┬───────────┬──────────────┬─────────┬──────────┘
   ▼           ▼              ▼         ▼
Stage 1      Stage 2        Stage 3   Stage 4
数据获取     指标计算        LLM决策   信号通知
(AKShare)   (Greeks/HV/IV) (Claude)  (企业微信)
   │           │              │          │
   └───────────┴──────┬───────┴──────────┘
                      ▼
               SQLite (历史记录/信号存档)
```

## 四阶段数据流

### Stage 1：数据获取 (`src/fetcher/`)

| 组件 | 说明 |
|------|------|
| `base.py` | 抽象基类，定义 `fetch_option_chain()` 和 `fetch_underlying_history()` 接口 |
| `akshare_fetcher.py` | AKShare 实现，ETF期权用 Sina 接口，商品期权用交易所日数据 |

**ETF 期权获取流程：**
1. `option_current_day_sse()` → 所有上市合约基本信息（Strike、到期日、类型）
2. 过滤：目标标的 + 近2个月 + ATM附近（±15%）→ 约30-50个合约
3. 逐个调用 `option_sse_greeks_sina()` → Delta/Gamma/Theta/Vega/IV

**商品期权获取流程：**
- `option_hist_czce()` / `option_hist_shfe()` → 批量获取，含 Delta + IV

### Stage 2：指标计算 (`src/compute/`)

| 模块 | 计算内容 |
|------|----------|
| `volatility.py` | 历史波动率 HV(10/20/60日)、IV分位数、IV Rank |
| `technicals.py` | MA(5/20/60)、RSI(14)、趋势判断 |
| `screener.py` | 候选合约筛选：成交量≥500、IV有效(≥1%)、Moneyness≤15%、到期≥7天 |

**关键压缩步骤：**
- 120条K线 → `hv10=18.5%, hv20=22.3%, hv60=25.1%`
- 50+个合约 → 10-15个高质量候选（含完整Greeks）

### Stage 3：LLM 分析 (`src/analyst/`)

| 组件 | 说明 |
|------|------|
| `base_llm.py` | LLM 抽象基类 |
| `claude_client.py` | Anthropic Claude 实现 |
| `zhipu_client.py` | 智谱 GLM 实现 |
| `llm_factory.py` | 根据 `LLM_PROVIDER` 环境变量创建实例 |
| `context_builder.py` | 将 OptionChain + VolatilityData + 候选合约 → MarketSnapshot JSON |
| `prompts.py` | 系统提示词（角色设定、策略框架、JSON输出格式要求） |
| `signal_parser.py` | 解析 LLM 返回的 JSON → TradingSignal 对象 |

**喂给 LLM 的数据结构（约 1-6KB，< 3000 tokens）：**

```json
{
  "scan_time": "2026-04-07 10:30:00",
  "underlying": {
    "code": "510050", "name": "50ETF", "price": 2.9,
    "change_pct": -0.03, "ma5": 2.92, "ma20": 2.95,
    "rsi14": 42.1, "trend": "neutral_bearish"
  },
  "volatility": {
    "hv10": 14.2, "hv20": 16.2, "hv60": 18.5,
    "iv_atm": 18.7, "iv_percentile": 65.0,
    "iv_vs_hv": "iv_premium(+2.5)"
  },
  "candidates": [
    {
      "code": "10011105", "type": "call", "strike": 2.95,
      "days_to_expiry": 15, "last_price": 0.025, "iv": 18.7,
      "greeks": {"delta": 0.32, "gamma": 3.94, "theta": -0.43, "vega": 0.21},
      "volume": 69498, "open_interest": 0
    }
    // ... 更多候选
  ]
}
```

**LLM 输出格式（JSON）：**

```json
{
  "market_assessment": "当前市场评判（2-3句）",
  "signals": [
    {
      "action": "sell_strangle",
      "legs": [{"code": "合约代码", "direction": "sell", "quantity": 1}],
      "rationale": "交易理由（引用具体数据）",
      "risk_warning": "风险提示和止损建议",
      "confidence": "high|medium|low",
      "urgency": "immediate|within_session|next_session"
    }
  ],
  "no_action_reasons": ["如无信号，说明原因"]
}
```

### Stage 4：通知 (`src/notify/`)

| 组件 | 说明 |
|------|------|
| `formatter.py` | 将 AnalysisResult → 人类可读中文消息 |
| `wechat.py` | 企业微信 Webhook POST（未配置时打印到终端） |

## 数据模型

```
MarketSnapshot          ← 喂给 LLM 的输入
  ├── underlying: dict  ← 标的摘要（价格/涨跌/技术指标）
  ├── volatility: dict  ← 波动率分析
  └── candidates: list  ← 筛选后的期权合约

AnalysisResult          ← LLM 输出解析结果
  ├── market_assessment ← 市场判断文字
  ├── signals: list     ← TradingSignal 列表
  └── no_action_reasons ← 无信号时的说明

TradingSignal
  ├── action            ← 策略类型
  ├── legs              ← 每腿操作（代码/方向/数量）
  ├── rationale         ← 推理说明
  ├── confidence        ← 信心等级
  └── urgency           ← 紧急程度
```

## 上下文窗口管理策略

| 层级 | 操作 | 结果 |
|------|------|------|
| 数据层 | 获取全量数据，只保留必要字段 | 原始 MB → 几十KB |
| 计算层 | 将时序数据归纳为统计指标 | 几十KB → 少量标量 |
| 上下文层 | 只将决策相关指标组装成 JSON | 最终 1-6KB |

Claude Sonnet 上下文足够，每次调用约 2000-4000 tokens，成本极低（全天扫描约 ¥0.5）。
