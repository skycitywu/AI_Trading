# GCE 部署手册

把一个长期运行的 Python 应用（守护进程、定时任务、Web 后端等）部署到 Google Cloud Engine (GCE) e2-micro 实例的完整流程。以本仓库 AI Trading Daemon 为例，但绝大部分内容对任何 Python 长驻服务都通用。

> 写作背景：第一次部署趟过几个坑（最大的就是 SSH 死活连不上），把经验沉淀下来，让后续上新机或类似项目的新手不用再踩。

---

## 1. 为什么用 GCE（而不是 Cloud Run / Functions / 本地 NAS）

| 场景 | 推荐方案 |
|------|----------|
| HTTP 请求触发、短时无状态任务 | **Cloud Run / Functions**（按调用计费，闲置零成本） |
| 长驻进程、需要进程内内存状态（如去重 Set、连接池、APScheduler） | **GCE 常驻 VM** ← 本项目用这个 |
| 一天跑几小时、剩下时间纯闲置 | **GCE + Cloud Scheduler 启停 VM** |
| 想跑本地家用机 | 可以，但要解决 NAT 穿透 / 公网 IP / 24×7 稳定性 |

**为什么本项目选 GCE**：APScheduler 跑在进程里，每 30 分钟轮询；信号去重靠进程内 `set`；同时 GCE 出口 IP 在境外，能稳定访问 AKShare / Anthropic / Google API。e2-micro 在美中区域有[免费层级](https://cloud.google.com/free)，本项目实际消耗约 $0。

---

## 2. 整体部署架构

```
你的本地电脑                                    Google Cloud
─────────────                                  ──────────────────────────────
                                               ┌─ Project: <your-project>
git push  ───┐                                 │
             │                                 │  ┌─ GCE VM (e2-micro)
GitHub ◄─────┘                                 │  │   instance-xxxxx, us-central1-a
   │                                           │  │   Debian 12
   │  git pull (在 VM 内)                      │  │
   └────────────────────────────────────────►  │  │   /home/<user>/AI_Trading/    ← 代码
                                               │  │   /home/<user>/venv/          ← Python 虚拟环境
gcloud compute ssh                             │  │   /etc/systemd/system/        ← ai-trading.service
   <instance> --tunnel-through-iap   ─────►   │  │
   (走 IAP 隧道, 不走公网 22 端口)             │  │   systemd 守护进程 24×7 运行
                                               │  │
                                               │  └─ 防火墙规则:
                                               │       allow-iap-ssh  TCP:22  from 35.235.240.0/20
                                               │
                                               └─
```

关键概念：
- **VM**：虚拟机本体
- **IAP (Identity-Aware Proxy)**：Google 的零信任代理，让你不开公网 22 端口也能 SSH 进 VM
- **systemd**：Linux 自带的服务管理器，负责拉起 / 重启 / 看日志

---

## 3. 第一次部署（from scratch）

### 3.1 创建 GCE 实例

在 Google Cloud Console 或本地命令行：

```bash
gcloud compute instances create my-app \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=30GB
```

> e2-micro 在 us-central1 / us-east1 / us-west1 三个区域有[免费配额](https://cloud.google.com/free)，磁盘 ≤30 GB。

### 3.2 ⚠️ 打通 SSH —— 最大的坑！

**默认情况下你 `gcloud compute ssh` 死活连不上**，因为：
- Google Cloud 出于安全考虑，**默认不允许外部 IP 直接通过 22 端口访问 VM**（哪怕你放了公钥）
- 它推荐使用 **IAP (Identity-Aware Proxy)**——Google 在你和 VM 之间加的"内网穿透堡垒机"

**正确连接流程**：

```
你本地电脑
  → 验证 Google 账号
  → Google 内部中转节点 (IP: 35.235.240.0/20)
  → 你的 VM 22 端口
```

**两步打通**：

**Step 1：在 GCP 防火墙开一个口子，允许 IAP 中转节点访问 22 端口**

```bash
gcloud compute firewall-rules create allow-iap-ssh \
  --direction=INGRESS \
  --action=allow \
  --rules=tcp:22 \
  --source-ranges=35.235.240.0/20
```

这句话的意思是："允许来自 Google 内部中转节点 (`35.235.240.0/20`) 的流量访问我所有 VM 的 22 端口。" 整个项目只需做一次。

**Step 2：每次 SSH 都加 `--tunnel-through-iap`**

```bash
gcloud compute ssh <instance-name> --zone us-central1-a --tunnel-through-iap
```

这告诉 `gcloud`："不要尝试直接连 VM 公网 IP，走 IAP 隧道"。

> 如果哪天你换了机器、清了 gcloud 配置，记住这两步必须重做（或者用更省事的：直接在 Console 网页里点 SSH，那个按钮默认就走 IAP）。

### 3.3 准备运行环境（在 VM 内）

```bash
# 装系统依赖
sudo apt update && sudo apt install -y python3 python3-venv git

# 创建虚拟环境（与代码目录分开，方便 systemd 指定固定路径）
python3 -m venv ~/venv

# 拉代码
git clone https://github.com/<you>/<repo>.git ~/AI_Trading
cd ~/AI_Trading

# 装依赖
~/venv/bin/pip install -r requirements.txt
```

> **为什么 venv 放在 `~/venv` 而不是 `~/AI_Trading/.venv`？** systemd 单元文件里要写绝对路径，与项目目录分开避免误删；多个项目可以共用同一个 venv，也可以各自一个。

### 3.4 配置 .env

```bash
cp .env.example .env
nano .env   # 填入真实 API key、Webhook 等
```

> **绝对不要把 .env commit 进 git**。先在 `.gitignore` 里有 `.env`，再来填值。

### 3.5 写 systemd 单元文件

新建 `/etc/systemd/system/ai-trading.service`：

```ini
[Unit]
Description=AI Trading Signal Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<your-linux-user>
WorkingDirectory=/home/<your-linux-user>/AI_Trading
ExecStart=/home/<your-linux-user>/venv/bin/python scripts/run_daemon.py
Restart=on-failure
RestartSec=60
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

关键点：
- `ExecStart` 必须是 **venv 内的 python 绝对路径**，不能写 `python3`
- `WorkingDirectory` 是项目根目录，应用读 `.env` 的相对路径靠它
- `PYTHONUNBUFFERED=1` 让 `print` / logging 立刻写出，不然 `journalctl` 看不到实时日志
- `Restart=on-failure` + `RestartSec=60` 让进程崩了自动 60 秒后重启
- 模板见仓库的 [deploy/ai-trading.service](../deploy/ai-trading.service)

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-trading      # 开机自启
sudo systemctl start ai-trading
sudo systemctl status ai-trading      # 看是否 active (running)
sudo journalctl -u ai-trading -f      # 跟踪日志
```

### 3.6 验证

```bash
# 进程在跑？
sudo systemctl is-active ai-trading   # 应输出 active

# 应用有输出？
sudo journalctl -u ai-trading -n 50 --no-pager

# VM 出口 IP 能访问外网？
curl -s ifconfig.me                   # 看你的出口 IP
curl -s https://www.google.com -o /dev/null -w "%{http_code}\n"  # 应输出 200
```

---

## 4. 日常迭代发布（最常用）

代码改完后上线，**永远走这五步**，不要现想：

```bash
INSTANCE=<your-instance>; ZONE=<your-zone>

# 1. 本地: 提交并推送 (注意只 add 本次相关文件)
git add <files...> && git commit -m "..." && git push origin master

# 2. GCE: 拉新代码
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "cd ~/AI_Trading && (git diff --quiet || git stash) && git pull"

# 3. GCE: 装新依赖（只在 requirements.txt 改了才跑）
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "/home/<user>/venv/bin/pip install -r ~/AI_Trading/requirements.txt"

# 4. GCE: 改 .env（只在新增 env 时；先备份，用 sed 精准改）
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "cd ~/AI_Trading && cp .env .env.bak.\$(date +%Y%m%d) && sed -i 's|^OLD_KEY=.*|NEW_KEY=value|' .env && diff .env.bak.\$(date +%Y%m%d) .env"

# 5. GCE: 重启 + 看日志
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "sudo systemctl restart ai-trading && sleep 3 && sudo systemctl status ai-trading --no-pager | head -15 && sudo journalctl -u ai-trading -n 20 --no-pager"
```

可以串成一条 `&&` 链一次执行；分步走的好处是某一步出错可以单独重试，不必整体回滚。

---

## 5. 日常运维

```bash
# 查服务状态
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "sudo systemctl status ai-trading --no-pager"

# 实时跟踪日志
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "sudo journalctl -u ai-trading -f"

# 看应用自己写的详细日志（包含 LLM prompt 等）
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "cat ~/AI_Trading/logs/daemon_\$(date +%Y%m%d).log"

# 重启服务
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "sudo systemctl restart ai-trading"

# 临时停服（不会自动重启）
gcloud compute ssh $INSTANCE --zone $ZONE --tunnel-through-iap --command \
  "sudo systemctl stop ai-trading"

# 查询实例信息
gcloud compute instances list
gcloud compute instances describe $INSTANCE --zone $ZONE
```

---

## 6. 趟过的坑 & 应对

| 现象 | 根因 | 应对 |
|------|------|------|
| `gcloud compute ssh` 一直卡住或报 `Connection timed out` | 默认 22 端口对外网关闭，且没启用 IAP 隧道 | 见 §3.2：建 IAP 防火墙规则 + 加 `--tunnel-through-iap` |
| `gcloud crashed (SSLError) ... UNEXPECTED_EOF_WHILE_READING` | IAP 隧道偶发抖动 / 跨境网络不稳 | 直接重试原命令。如果一直失败，检查本地代理 |
| `git pull` 报 `Your local changes would be overwritten by merge` | 服务器上有未提交的本地修改（之前手动改过文件） | `git diff` 看是什么；若无价值 `git stash` 后再 pull，最后 `git stash drop` |
| `systemctl status` 显示 `active (running)` 但应用没在工作 | 进程被卡死、外部依赖挂了，systemd 看不出来 | 看 `journalctl` 找最近的异常；本项目曾因 akshare 一个 HTTP 调用没有 timeout 而把 APScheduler 卡了 23 天（commit `9da8ff4` 加了 `concurrent.futures` 包一层 timeout）|
| 改了 `.env` 后服务读不到新值 | systemd 不会自动重新读 .env | `sudo systemctl restart ai-trading` |
| 重启后 .env 里的密钥全丢了 | 用 `cat > .env` 或编辑器粘贴时漏了某些行 | **永远先 `cp .env .env.bak.YYYYMMDD-原因`**；优先用 `sed -i` 改单行而不是整体覆盖；如果必须重写，先 `cat` 旧文件全文确认有哪些字段 |
| `pip install` 装到了系统 Python 而不是 venv | 直接打 `pip install ...` 而不是 venv 内的 pip | 永远写绝对路径：`/home/<user>/venv/bin/pip install ...`；或先 `source ~/venv/bin/activate` |
| systemd 起来后看不到 logging 输出 | Python 默认行缓冲，日志卡在内存里 | 单元文件加 `Environment=PYTHONUNBUFFERED=1`（或代码里加 `logging.basicConfig(..., force=True)`）|
| `ExecStart` 写 `python3` 报 `ModuleNotFoundError` | systemd 跑的是系统 python，没装你的依赖 | 必须写 venv 里 python 的**绝对路径** |
| VM 重启后服务没自动起来 | 没 enable | `sudo systemctl enable ai-trading` |
| 出口被某些境内 API 拒绝 / 数据接口 403 | GCE 出口 IP 是境外的 | 换数据源；或者用境内云（阿里/腾讯）部署；或加代理 |

---

## 7. 安全 / 成本提醒

- **不要把 `.env` 提交进 git**。`.gitignore` 必须有它。
- **不要把实例名、project ID 写进公开 README**。本仓库做了脱敏处理（commit `d3a3987`）。需要的话用 `gcloud compute instances list` 实时查。
- **e2-micro 免费配额**：每月 1 个 `f1-micro` (退役) 或 `e2-micro` 在 us-central1/east1/west1 区域、≤30GB 磁盘；超出按需计费，金额很小但要注意账单告警。
- **IAP 防火墙规则的 source-ranges 必须严格写 `35.235.240.0/20`**，不要图省事写 `0.0.0.0/0`（那等于把 22 暴露给全世界）。
- **日志会无限增长**：journalctl 默认 systemd 有 rotate，但应用自己写的 `logs/*.log` 没有。本仓库现在每天一个文件 (`daemon_YYYYMMDD.log`)，长期跑要定期清理 / logrotate。

---

## 8. 进阶（按需用）

- **多实例部署 / 滚动发布**：弄个 [Instance Group](https://cloud.google.com/compute/docs/instance-groups)，配合 health check。本项目用不到。
- **代码部署用 Cloud Build + Artifact Registry**：把"push → SSH → pull"换成"push → CI 自动构建容器镜像 → VM 拉镜像"。门槛比 git pull 高，长期看更规范。
- **配置管理用 Secret Manager**：把 `.env` 里的 key 移到 Secret Manager，VM 启动时拉取。比文件安全，但增加运维复杂度。
- **监控告警**：用 Cloud Monitoring 配 alerting policy，进程挂了 / 日志报错 / CPU 飙高就给手机推送。

---

## 9. 速查命令清单

```bash
# 一次性设置（首次部署）
gcloud compute firewall-rules create allow-iap-ssh \
  --direction=INGRESS --action=allow --rules=tcp:22 \
  --source-ranges=35.235.240.0/20

# 列实例
gcloud compute instances list

# SSH（每次必加 --tunnel-through-iap）
gcloud compute ssh <instance> --zone <zone> --tunnel-through-iap

# 一行远程执行
gcloud compute ssh <instance> --zone <zone> --tunnel-through-iap --command "..."

# 服务管理
sudo systemctl {start|stop|restart|status|enable|disable} <service>
sudo journalctl -u <service> {-f|-n 50|--no-pager}
```

完。
