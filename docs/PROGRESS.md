# 项目进度

## 当前状态：Phase 1 完整打通，企业微信通知上线 ✅

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

### Phase 1.5：首次真实运行 + 通知打通（2026-04-08）
- [x] 修复 `requirements.txt`：`py_vollib` 版本约束从 `>=1.0.3` 改为 `>=1.0.0`（PyPI 最新只有 1.0.1）
- [x] LLM 配置外部化：`config/settings.py` 新增 `llm_api_base_url` / `llm_model` 字段，从 `.env` 读取，不再硬编码
- [x] ETF 数据获取增强：`fund_etf_hist_em`（东方财富） → `stock_zh_a_hist` → `fund_etf_hist_sina`（新浪）三级降级，解决东方财富接口偶发断连
- [x] ETF 标的价格兜底：三级接口全失败时，从 Delta≈0.5 的 ATM 合约行权价估算标的价格
- [x] 文件日志：每次运行在 `logs/` 下生成带时间戳的 `.log` 文件，终端输出 INFO，文件记录 DEBUG（含提示词、LLM 原始返回）
- [x] 信号详情打印：`run_once.py` 末尾打印市场评估 + 信号腿/理由/风险提示
- [x] 全流程真实验证：GLM-4.5-air 成功返回信号（sell strangle 50ETF，IV分位72%）
- [x] 企业微信通知打通：配置群机器人 Webhook（企业微信"消息推送"功能，原"群机器人"）
- [x] 通知格式优化：合约操作腿显示名称（如"50ETF沽4月3000"）而非纯数字代码；urgency 字段汉化（within_session→当日内等）
  - 修改范围：`SignalLeg` 加 `name` 字段、LLM prompt schema 加 `name`、`signal_parser` 解析 `name`、`formatter` 加 `URGENCY_MAP`

---

## 已知问题 / 技术债

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| 东方财富接口偶发断连 | 低 | 已增加三级降级：em → stock_zh_a_hist → fund_etf_hist_sina；价格全失败时从ATM行权价估算 |
| DCE 大商所接口不可用 | 低 | 豆粕期权暂时移除，可定期测试是否恢复 |
| SHFE 铜期权无 IV | 低 | 需单独调用 `option_vol_shfe()` 补充 |
| ETF OI 为 0 | 低 | Sina Greeks 接口不含持仓量，已在筛选器中处理（OI=0时跳过OI过滤） |
| 历史 IV 数据缺失 | 中 | IV 分位数目前用 HV 序列近似，准确性有限 |
| 无持久化存储 | 低 | Phase 2 添加 SQLite |
| 无定时调度 | 低 | Phase 2 添加 APScheduler |

---

## 下一步（Phase 2）

优先级从高到低：

1. **[x] 完整测试**：配置真实 LLM API key（智谱 GLM-4.5-air），全流程跑通，信号质量待持续评估
2. **[x] 企业微信通知**：配置真实 Webhook URL，验证通知推送，优化消息格式
3. **[ ] 定时盯盘（高优先）**：实现 `scripts/run_daemon.py`，使用 APScheduler 或 cron，在交易时段定时扫描
4. **[ ] 云端部署（高优先）**：部署到 Google Cloud（Cloud Run 或 GCE），实现 7×24 盯盘
5. **[ ] 信号去重**：避免同一机会在多次扫描中重复推送（需持久化支持）
6. **[ ] SQLite 持久化**：实现 `src/database/`，存储历史信号，支持去重和回顾
7. **[ ] 信号冲突检测**：同一报告内多个信号方向互相矛盾时告警或过滤（如 buy_put + sell_strangle 同时出现）
8. **[ ] SHFE 铜 IV 补充**：集成 `option_vol_shfe()` 获取隐含波动率
9. **[ ] 历史 IV 数据**：接入 QVIX 或其他历史 IV 数据源，提升 IV 分位数准确性

## Phase 3 规划

1. **[ ] Pobo 桥接探索**：测试 Pobo 平台内是否支持 HTTP 请求，建立数据桥接
2. **[ ] DCE 大商所恢复**：待接口可用后重新接入豆粕期权
3. **[ ] 多 Agent 分析**：针对复杂市场，引入多轮 LLM 对话（看多/看空辩论机制）
4. **[ ] 回测框架**：评估历史信号质量
5. **[ ] 盯盘 Dashboard**：简单 Web 页面展示历史信号

---

## 云端部署备忘（Phase 2 重点）

目标平台：**Google Cloud**，推荐方案：
- **Cloud Run**（无服务器，按需计费）：适合低频定时触发（配合 Cloud Scheduler）
- **GCE e2-micro**（永久免费档）：适合常驻守护进程，每天交易时段内循环扫描

关键注意事项：
- 中国市场数据（AKShare/Sina）需确认 GCP 出口 IP 未被封锁，必要时加代理
- 时区设置为 `Asia/Shanghai`，避免盯盘时段判断错误
- 企业微信 Webhook 无需公网入口，直接从 GCP 外出调用即可
