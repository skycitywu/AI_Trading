# 项目进度

## 当前状态：Phase 2 云端自动盯盘部署完成 ✅

---

## 已完成（Phase 1 & 2）

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

### Phase 2：自动盯盘与云端部署（2026-04-11）
- [x] 多渠道通知集成：新增 PushPlus 渠道，支持 `src/notify/dispatcher.py` 统一分发到微信群和个人微信
- [x] 扫描结果聚合：将单轮 4 个标的的扫描结果聚合成一条推送消息（`format_scan_round`），避免连续发信刷屏
- [x] GCE 服务器部署：通过 GCP IAP 隧道连接，全自动化克隆代码、建立 venv 并运行 `requirements.txt`
- [x] Systemd 守护进程：配置 `ai-trading.service` 注册为系统级服务，实现开机自启、崩溃重启、脱离终端 24 小时后台运行

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

## 下一步（Phase 3）

优先级从高到低：

1. **[ ] SQLite 持久化**：实现 `src/database/`，存储历史信号，支持基于持久化的防重复推送，支持历史回溯
2. **[ ] 信号冲突检测**：同一报告内多个信号方向互相矛盾时告警或过滤（如 buy_put + sell_strangle 同时出现）
3. **[ ] 调度优化**：按用户需求将 `IntervalTrigger` 改为 `CronTrigger`，使轮询对齐自然时钟（如 :00 和 :30）
4. **[ ] SHFE 铜 IV 补充**：集成 `option_vol_shfe()` 获取隐含波动率
5. **[ ] 历史 IV 数据**：接入 QVIX 或其他历史 IV 数据源，提升 IV 分位数准确性

## Phase 4 规划

1. **[ ] Pobo 桥接探索**：测试 Pobo 平台内是否支持 HTTP 请求，建立数据桥接
2. **[ ] DCE 大商所恢复**：待接口可用后重新接入豆粕期权
3. **[ ] 多 Agent 分析**：针对复杂市场，引入多轮 LLM 对话（看多/看空辩论机制）
4. **[ ] 回测框架**：评估历史信号质量
5. **[ ] 盯盘 Dashboard**：简单 Web 页面展示历史信号

---

## 云端部署备忘

### 已部署完成方案：GCE e2-micro 常驻进程（2026-04-11）

- **机型**：e2-micro，us-central1（Iowa），Debian 12
- **连接方式**：绕过原生 SSH 报错限制，通过 GCP IAP (Identity-Aware Proxy) 隧道打通 `gcloud compute ssh` 访问
- **依赖环境**：系统不自带 `python3-venv`，已执行 `sudo apt-get install python3-venv`。运行目录为 `~/AI_Trading`
- **进程管理**：使用 systemd 配置守护进程 `ai-trading.service`，实现崩溃重启和开机启动
- **日志管理**：通过 `journalctl -u ai-trading -f` 查看实时 stdout 日志，也可以使用 `cat logs/daemon_xxx.log` 查看文件内的 DEBUG 明细
