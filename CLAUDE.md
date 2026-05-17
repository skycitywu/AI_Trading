# AI Trading — Claude Code 项目指引

## 项目一句话描述

AI 驱动的中国期权市场交易信号 Agent：自动获取行情、计算指标、用 LLM 分析机会、发出交易提醒（不自动下单）。

## 核心设计原则

**确定性代码负责数据和计算，LLM 负责分析和决策。**

大量原始市场数据经过三层压缩后才喂给模型（原始数据 → 计算指标 → 结构化 JSON 摘要，最终约 1-3KB），解决了上下文窗口限制问题。

## 关键文档（必读）

| 文档 | 内容 |
|------|------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统架构、数据流、各模块分工 |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | AKShare 接口调研：哪些可用/不可用、字段说明 |
| [docs/STRATEGY.md](docs/STRATEGY.md) | 期权交易策略说明 |
| [docs/PROGRESS.md](docs/PROGRESS.md) | 项目进度、已完成事项、下一步计划 |
| [docs/GCE_DEPLOYMENT.md](docs/GCE_DEPLOYMENT.md) | GCE 部署完整手册（首次部署 + 迭代发布 + 坑总结） |

## 技术栈速览

- **Python 3.9+**（注意：需要 `from __future__ import annotations` 兼容类型注解）
- **数据源**：AKShare（免费，中国期权市场）
- **LLM**：支持 Claude API (Anthropic)、智谱 GLM、Google Gemini，通过 `LLM_PROVIDER` 环境变量切换
- **配置**：pydantic-settings，从 `.env` 读取

## 开发命令

```bash
# 1. 配置环境
cp .env.example .env
# 编辑 .env，填入 API key

# 2. 安装依赖
pip install -r requirements.txt

# 3. 测试数据获取（不需要 API key）
python3 scripts/run_once.py --dry-run --code 510050

# 4. 全流程 Mock 测试（不需要 API key）
python3 scripts/run_once.py --mock-llm --code 510050

# 5. 真实运行单次扫描
python3 scripts/run_once.py --code 510050

# 6. 扫描所有监控标的
python3 scripts/run_once.py

# 7. 只扫描 ETF 期权
python3 scripts/run_once.py --etf

# 8. 只扫描商品期权
python3 scripts/run_once.py --commodity

# 9. 启动定时盯盘守护进程（交易时段自动扫描）
python3 scripts/run_daemon.py

# 10. 守护进程只盯特定标的
python3 scripts/run_daemon.py --code 510050
```

## 项目结构

```
AI_Trading/
├── CLAUDE.md              ← 你在这里
├── .env.example           # 环境变量模板
├── requirements.txt
├── config/
│   ├── settings.py        # 全局配置（pydantic-settings）
│   ├── instruments.py     # 监控标的列表（可增删）
│   └── strategies.py      # 策略参数阈值
├── src/
│   ├── fetcher/           # Stage 1: 数据获取
│   ├── compute/           # Stage 2: 指标计算（HV/IV/Greeks/筛选）
│   ├── analyst/           # Stage 3: LLM 分析决策
│   ├── notify/            # Stage 4: 通知（企业微信 + PushPlus）
│   ├── pipeline/          # 编排器（串联四阶段）
│   ├── models/            # 数据模型（dataclass）
│   └── database/          # SQLite 持久化（Phase 2）
├── scripts/
│   ├── run_once.py        # 手动触发入口
│   └── run_daemon.py      # 定时守护进程（APScheduler + 交易时段判断 + 信号去重）
├── deploy/
│   └── ai-trading.service # systemd 单元文件（GCE 部署用）
├── docs/                  # 项目文档
└── tests/
```

## 重要注意事项

### 数据源稳定性
- **Sina 新浪接口**（ETF期权 Greeks/行情、ETF历史日线）：稳定可用
- **东方财富(em)接口**：偶尔连接被断；ETF 历史数据已实现三级降级（em → stock_zh_a_hist → fund_etf_hist_sina），自动切换
- **CZCE/SHFE 交易所日数据**：稳定，含 Delta + IV
- **DCE 大商所接口**：当前不可用（JSON decode error），豆粕期权暂时移除
- 详见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)

### LLM 配置
```env
# 用 Claude
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxx
LLM_MODEL=claude-sonnet-4-20250514   # 可选，留空用默认值

# 用智谱 GLM
LLM_PROVIDER=zhipu
ZHIPU_API_KEY=xxx
LLM_API_BASE_URL=https://open.bigmodel.cn/api/paas/v4  # 可选，留空用默认值
LLM_MODEL=glm-4.5-air               # 可选，留空用默认值

# 用 Gemini (Google AI Studio)
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3-flash-preview     # 或 gemini-3.1-pro-preview (需付费 key)
GEMINI_API_KEY=AIza...               # 在 .env 中切换免费/付费 key 即可
```

> 说明：免费 key 只能用 Flash / Flash-Lite 系列，Pro 系列会 429；付费 key 全部可用。要切换 key，直接改 `.env` 里的 `GEMINI_API_KEY` 值。

### 通知渠道配置
支持企业微信和 PushPlus 两个渠道，可同时启用。两个都不配置时，通知内容打印到终端。

**企业微信**（内部群机器人）：
```env
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key
```

**PushPlus**（微信公众号推送，适合外部用户）：
1. 关注"pushplus推送加"公众号，登录官网获取 Token
2. 创建群组，将群组码分享给接收人（接收人也需关注该公众号并订阅群组）
```env
PUSHPLUS_TOKEN=你的token
PUSHPLUS_TOPIC=群组码   # 不填则只推给自己
```

### 新增监控标的
编辑 [config/instruments.py](config/instruments.py)，按格式添加 `Underlying` 对象即可。

### 修改策略参数
编辑 [config/strategies.py](config/strategies.py)，调整 IV 分位数阈值、流动性过滤条件等。

---

## GCE 部署更新（迭代发布 playbook）

线上运行在 GCE：systemd 服务 `ai-trading.service`，工作目录 `/home/wufeng/AI_Trading`，venv `/home/wufeng/venv`，SSH 必须走 IAP 隧道。实例名/区域用 `gcloud compute instances list` 查；首次部署、坑总结见 [docs/GCE_DEPLOYMENT.md](docs/GCE_DEPLOYMENT.md)。

**每次代码改动上线就按这五步走，别重新探索：**

```bash
INSTANCE=<your-instance>; ZONE=<your-zone>   # 用 gcloud compute instances list 查

# 1. 本地: 提交并推送 (只 add 本次相关文件, 别把无关 WIP 顺手带上)
git add <相关文件...> && git commit -m "..." && git push origin master

# 2. GCE: 拉新代码 (服务器有未提交本地改动时先 stash, 避免 pull 被 abort)
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "cd ~/AI_Trading && (git diff --quiet || git stash) && git pull"

# 3. GCE: 装新依赖 (只在 requirements.txt 改了才跑)
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "/home/wufeng/venv/bin/pip install -r ~/AI_Trading/requirements.txt"

# 4. GCE: 改 .env (只在新增/改 env 时; 必须先备份, 用 sed 精准改单行, 别整体覆盖)
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "cd ~/AI_Trading && cp .env .env.bak.$(date +%Y%m%d) && sed -i 's|^X=old\$|X=new|' .env && diff .env.bak.$(date +%Y%m%d) .env"

# 5. GCE: 重启 + 看日志确认
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "sudo systemctl restart ai-trading && sleep 3 && sudo systemctl status ai-trading --no-pager | head -15 && sudo journalctl -u ai-trading -n 20 --no-pager"
```

**高频坑（详见 GCE_DEPLOYMENT.md）：**
- `gcloud crashed (SSLError) UNEXPECTED_EOF_WHILE_READING`：IAP 隧道抖动，原命令重试即可。
- `Your local changes would be overwritten by merge`：服务器有未提交修改。先 `git diff` 确认无价值，再 `git stash` 然后 pull，最后 `git stash drop`。
- **永远不要在远程整体覆盖 .env**（会丢已有 token/key）。用 sed 改单行 + `.env.bak.YYYYMMDD-原因` 备份。
- 旧 provider 配置注释保留在 .env 里作回退（如智谱配置）—— 不要直接删。
