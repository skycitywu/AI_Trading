# 项目进度

## 当前状态：Phase 1 MVP 完成 ✅

---

## 已完成（Phase 1）

### 基础设施
- [x] 项目结构搭建（config / src / scripts / docs / tests）
- [x] 环境配置（pydantic-settings，`.env.example`，`.gitignore`）
- [x] Python 3.9 兼容性处理（`from __future__ import annotations`）

### Stage 1：数据获取
- [x] `src/fetcher/base.py` — 抽象基类
- [x] `src/fetcher/akshare_fetcher.py` — AKShare 实现
  - [x] ETF 期权：SSE 合约列表 + Sina Greeks/IV（逐合约）
  - [x] 商品期权：CZCE 白糖、SHFE 铜（批量，含Delta+IV）
  - [x] ETF 历史日线（用于计算 HV）
  - [x] 商品期货主力合约历史日线

### Stage 2：指标计算
- [x] `src/compute/volatility.py` — HV(10/20/60日)、IV分位数、IV Rank
- [x] `src/compute/technicals.py` — MA(5/20/60)、RSI(14)、趋势判断
- [x] `src/compute/screener.py` — 候选合约筛选（流动性、Moneyness、DTE、IV有效性）

### Stage 3：LLM 分析
- [x] `src/analyst/base_llm.py` — LLM 抽象基类
- [x] `src/analyst/claude_client.py` — Anthropic Claude 实现
- [x] `src/analyst/zhipu_client.py` — 智谱 GLM 实现
- [x] `src/analyst/llm_factory.py` — 多模型工厂
- [x] `src/analyst/prompts.py` — 系统提示词 + 用户提示词模板
- [x] `src/analyst/context_builder.py` — MarketSnapshot → JSON
- [x] `src/analyst/signal_parser.py` — LLM JSON 输出解析

### Stage 4：通知
- [x] `src/notify/formatter.py` — 信号格式化（中文，含emoji）
- [x] `src/notify/wechat.py` — 企业微信 Webhook

### 流水线
- [x] `src/pipeline/orchestrator.py` — 串联四阶段
- [x] `scripts/run_once.py` — 手动入口（支持 --dry-run / --mock-llm / --code）

### 验证
- [x] 数据获取测试：50ETF 42个合约，白糖178个，铜434个
- [x] 四阶段端到端 Mock 测试通过（上下文约 6KB，< 3000 tokens）

---

## 已知问题 / 技术债

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| 东方财富接口偶发断连 | 中 | 影响 ETF 历史行情和实时行情，目前 ETF 价格用历史最新K线替代 |
| DCE 大商所接口不可用 | 低 | 豆粕期权暂时移除，可定期测试是否恢复 |
| SHFE 铜期权无 IV | 低 | 需单独调用 `option_vol_shfe()` 补充 |
| ETF OI 为 0 | 低 | Sina Greeks 接口不含持仓量，已在筛选器中处理（OI=0时跳过OI过滤） |
| 历史 IV 数据缺失 | 中 | IV 分位数目前用 HV 序列近似，准确性有限 |
| 无持久化存储 | 低 | Phase 2 添加 SQLite |
| 无定时调度 | 低 | Phase 2 添加 APScheduler |

---

## 下一步（Phase 2）

优先级从高到低：

1. **[ ] 完整测试**：配置真实 LLM API key，跑完整流水线，评估信号质量
2. **[ ] SHFE 铜 IV 补充**：集成 `option_vol_shfe()` 获取隐含波动率
3. **[ ] 历史 IV 数据**：接入 QVIX 或其他历史 IV 数据源，提升 IV 分位数准确性
4. **[ ] SQLite 持久化**：实现 `src/database/`，存储历史信号
5. **[ ] APScheduler 定时任务**：实现 `scripts/run_daemon.py`
6. **[ ] 信号去重**：避免同一机会在多次扫描中重复推送

## Phase 3 规划

1. **[ ] Pobo 桥接探索**：测试 Pobo 平台内是否支持 HTTP 请求，建立数据桥接
2. **[ ] DCE 大商所恢复**：待接口可用后重新接入豆粕期权
3. **[ ] 多 Agent 分析**：针对复杂市场，引入多轮 LLM 对话（看多/看空辩论机制）
4. **[ ] 回测框架**：评估历史信号质量
5. **[ ] 盯盘 Dashboard**：简单 Web 页面展示历史信号
