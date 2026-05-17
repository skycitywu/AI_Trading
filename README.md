# AI Trading Agent

基于 LLM 的中国期权市场智能盯盘与交易信号生成系统。该系统自动获取市场行情，计算高阶指标（Greeks、HV、IV 分位数），然后通过压缩后的核心数据驱动 LLM 进行决策，最终将交易信号推送到微信。

目前已完美运行在 Google Cloud (GCE) 上，实现 24 小时无人值守。

---

## 🏗 核心架构与流程

系统采用 **"确定性代码负责计算，LLM 负责决策"** 的设计理念，有效避免了 LLM 处理大量数据的幻觉问题和上下文长度限制。

一次完整的扫描流程（Stage 1-4）如下：

1. **获取数据 (Fetch)**: 通过 AKShare 抓取标的历史 K 线和期权链实时数据（数十个合约的 T 型报价）。
2. **计算指标 (Compute)**: 计算历史波动率(HV)、提取隐含波动率(IV)，计算 IV 分位数，并通过成交量、Moneyness 等条件筛选出优质候选合约（压缩数据）。
3. **LLM 分析 (Analyze)**: 将筛选后的标的指标和候选合约封装为极简的 JSON Snapshot（通常仅 1-3KB），连同 System Prompt 喂给 LLM。LLM 返回结构化的 JSON 交易信号。
4. **消息通知 (Notify)**: 将信号格式化为带 Emoji 的可读文本，按配置分发到企业微信或 PushPlus（支持合集推送防刷屏）。

> **定时策略**：服务器上通过 APScheduler 实现守护进程。每 30 分钟轮询一次。如果当前时间不在 A 股交易时段（9:30-11:30, 13:00-15:00），则自动跳过。同一标的的相同信号在当日内会自动去重。

---

## 📡 数据源说明

所有数据均通过免费接口获取，并做了完备的降级处理：

- **ETF 期权 (50ETF, 300ETF)**
  - 期权链与 Greeks：Sina 新浪接口（稳定）
  - 标的历史日线：实现三级降级（东方财富 -> 东方财富备用 -> 新浪），新浪极为稳定。若全失败则从期权链 ATM 行权价反推标的价格。
- **商品期权**
  - CZCE（郑商所）：如白糖。官方日线数据稳定，自带 Delta 和 IV。
  - SHFE（上期所）：如铜。官方数据稳定，含 Delta。
  - DCE（大商所）：如豆粕。当前 AKShare 接口存在 JSON 解析异常，暂时移除。

---

## 🚀 部署后的运行效果

当前部署在 Google Cloud Engine (e2-micro, Debian 12) 上。

- **自动休眠与唤醒**：在非交易时间（如凌晨、周末）只会打印 "跳过扫描"，不消耗 API 额度。
- **极低的 Token 消耗**：得益于数据高度压缩，每次 LLM 调用仅需 2000-3000 Tokens。每轮扫描 4 个标的，一天运行 8 轮，日总消耗不足 10 万 Tokens。
- **防刷屏推送**：每轮扫描（涵盖所有标的）的信号会被收集，合并成一条精简的消息推送到手机。

---

## 🛠 日常运维指南

### 1. 修改系统配置 (环境变量)

系统核心配置通过 `~/AI_Trading/.env` 文件控制。

```bash
# 1. 登录云服务器
gcloud compute ssh 你的实例名 --zone us-central1-a --tunnel-through-iap

# 2. 编辑环境变量
nano ~/AI_Trading/.env

# 3. 重启服务使配置生效
sudo systemctl restart ai-trading
```

### 2. 切换 LLM 模型

在 `.env` 中修改：
```ini
# 使用 Google Gemini (当前默认)
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
LLM_MODEL=gemini-3-flash-preview  # 免费 key 可用, 1M 上下文
# Pro 系列示例: LLM_MODEL=gemini-3.1-pro-preview (需付费 Tier 1 key)

# 使用智谱 GLM
# LLM_PROVIDER=zhipu
# ZHIPU_API_KEY=你的_API_KEY
# LLM_API_BASE_URL=https://open.bigmodel.cn/api/paas/v4
# LLM_MODEL=glm-4.5-air

# 使用 Anthropic Claude
# LLM_PROVIDER=claude
# ANTHROPIC_API_KEY=sk-ant-...
# LLM_MODEL=claude-sonnet-4-20250514
```

### 3. 配置通知渠道

系统支持双渠道同时推送，在 `.env` 中填入对应的值即可开启：
- **企业微信内部群**：填入 `WECHAT_WEBHOOK_URL`
- **个人微信/外部群**：使用 PushPlus。填入 `PUSHPLUS_TOKEN`。若推送到群组则填入 `PUSHPLUS_TOPIC`。

### 4. 查看运行状态与日志

在本地终端通过 gcloud 直接查看云端日志：

```bash
# 查看服务状态
gcloud compute ssh 你的实例名 --zone us-central1-a --tunnel-through-iap --command "sudo systemctl status ai-trading --no-pager"

# 实时查看最新运行日志 (追踪 LLM 调用和扫描进度)
gcloud compute ssh 你的实例名 --zone us-central1-a --tunnel-through-iap --command "sudo journalctl -u ai-trading -f"

# 查看完整的历史 Debug 日志 (包含发给 LLM 的原始 Prompt)
gcloud compute ssh 你的实例名 --zone us-central1-a --tunnel-through-iap --command "cat ~/AI_Trading/logs/daemon_$(date +%Y%m%d).log"
```

### 5. 调整扫描频率或目标

- **修改监控标的**：编辑 `config/instruments.py`，增删 `Underlying` 对象。
- **调整扫描间隔**：编辑 `.env`，添加 `SCAN_INTERVAL_MINUTES=15`（默认 30）。
- **改为对齐自然时间（如整点/半点）**：修改 `scripts/run_daemon.py`，将 `IntervalTrigger` 替换为 `CronTrigger(minute="0,30")`。修改代码后记得在服务器执行 `git pull` 并重启服务。

---

## 📝 待办事项 (Phase 2 & 3)

- **信号冲突检测**：LLM 偶尔会在同一报告中给出方向矛盾的信号（如同时卖出宽跨和买入看涨），需在解析层添加冲突过滤。
- **持久化**：引入 SQLite 替代现有的内存 Set 去重，记录历史交易信号用于回测。
- **实时盯盘**：目前为 30 分钟定时轮询，后续若需要实时破位提醒，需引入流式行情处理框架。
