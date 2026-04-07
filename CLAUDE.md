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

## 技术栈速览

- **Python 3.9+**（注意：需要 `from __future__ import annotations` 兼容类型注解）
- **数据源**：AKShare（免费，中国期权市场）
- **LLM**：支持 Claude API (Anthropic) 和 智谱 GLM，通过 `LLM_PROVIDER` 环境变量切换
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
│   ├── notify/            # Stage 4: 企业微信通知
│   ├── pipeline/          # 编排器（串联四阶段）
│   ├── models/            # 数据模型（dataclass）
│   └── database/          # SQLite 持久化（Phase 2）
├── scripts/
│   ├── run_once.py        # 手动触发入口
│   └── run_daemon.py      # 定时守护进程（Phase 2）
├── docs/                  # 项目文档
└── tests/
```

## 重要注意事项

### 数据源稳定性
- **Sina 新浪接口**（ETF期权 Greeks/行情）：稳定可用
- **东方财富(em)接口**：偶尔连接被断，影响 ETF 历史行情获取
- **CZCE/SHFE 交易所日数据**：稳定，含 Delta + IV
- **DCE 大商所接口**：当前不可用（JSON decode error），豆粕期权暂时移除
- 详见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)

### LLM 配置
```env
# 用 Claude
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxx

# 用智谱 GLM
LLM_PROVIDER=zhipu
ZHIPU_API_KEY=xxx
```

### 新增监控标的
编辑 [config/instruments.py](config/instruments.py)，按格式添加 `Underlying` 对象即可。

### 修改策略参数
编辑 [config/strategies.py](config/strategies.py)，调整 IV 分位数阈值、流动性过滤条件等。
