# DINQ Production Deployment (Analysis Service)

本仓库的分析服务采用 **单机本地优先** 的部署形态：
- API 进程内启动 scheduler 并执行 cards（爬虫/LLM）
- 主存储为本机 SQLite（jobs + analysis caches）
- 远程 Postgres（可选）仅用于 outbox 异步备份/冷启动读回（不在在线请求关键路径）

---

## 1) 前置条件

- Ubuntu + `systemd`
- Python 3 + `venv`
- DB：本机 SQLite（必需）；Postgres（可选，作为备份）
- `psql`（可选；仅当你要初始化/维护 Postgres 备份库表时需要）
- 配置文件：`.env.production`（推荐将敏感项放 `.env.production.local`）

---

## 2) 生产部署推荐流程（deploy.sh）

在服务器上（例如 `/root/dinq-dev`）：

```bash
cd /root/dinq-dev
./deploy.sh setup
./deploy.sh migrate
./deploy.sh install
./deploy.sh start
```

常用运维：

```bash
./deploy.sh status
./deploy.sh logs
```

一键更新（拉代码 + 装依赖 + migrate + 重启）：

```bash
sudo ./deploy.sh update
```

---

## 3) 关键配置要点

- `.env.production`：务必设置各类 API keys（不要提交到仓库）
- 主库（SQLite）：可选覆盖 `DINQ_JOBS_DB_URL` / `DINQ_CACHE_DB_URL`（默认会使用本机 SQLite 文件）
- 备份库（Postgres，可选）：设置 `DINQ_BACKUP_DB_URL`（或沿用 `DATABASE_URL` 作为兼容 fallback）
- systemd 环境：部署脚本默认写入
  - `DINQ_ENV=production` / `FLASK_ENV=production`
- SSE 连接数：建议 `LimitNOFILE=65535`
- gunicorn：建议 `--worker-class gthread`，根据机器内存调整 `--workers/--threads`

---

## 4) 安全建议

如果分析服务不再做 shared-secret（仅信任 Gateway 注入 `X-User-ID`），请务必在网络层限制：
- `:8080` 仅允许 Gateway 机器访问（或仅允许内网）
