# DINQ Production Deployment (Analysis Service + Runner)

本仓库的“新分析服务（dinq-dev）”推荐使用 **systemd + gunicorn + 独立 runner** 的部署形态：

- **API 进程**：只做 `POST create job / GET snapshot / SSE replay`
- **Runner 进程**：从 DB claim cards 执行（爬虫/LLM），写入 `job_events`（SSE 可回放/可续传）

> 旧的 `dinq_service.py` / `dinq.sh` 属于历史管理方式，不建议用于 dinq-dev（dev 分支）新架构。

---

## 1) 前置条件

- Ubuntu + `systemd`
- Python 3 + `venv`
- DB：Postgres（推荐）
- `psql`（用于运行 SQL migrations）
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
./deploy.sh start-runner
```

常用运维：

```bash
./deploy.sh status
./deploy.sh status-runner
./deploy.sh logs
./deploy.sh logs-runner
```

一键更新（拉代码 + 装依赖 + migrate + 重启）：

```bash
sudo ./deploy.sh update
```

---

## 3) 关键配置要点

- `.env.production`：务必设置 `DINQ_DB_URL` / `DATABASE_URL` + 各类 API keys（不要提交到仓库）
- systemd 环境：部署脚本默认写入
  - `DINQ_ENV=production` / `FLASK_ENV=production`
  - API：`DINQ_EXECUTOR_MODE=external`
  - Runner：`DINQ_EXECUTOR_MODE=runner`
- SSE 连接数：建议 `LimitNOFILE=65535`
- gunicorn：建议 `--worker-class gthread`，根据机器内存调整 `--workers/--threads`

---

## 4) 安全建议

如果分析服务不再做 shared-secret（仅信任 Gateway 注入 `X-User-ID`），请务必在网络层限制：
- `:8080` 仅允许 Gateway 机器访问（或仅允许内网）
