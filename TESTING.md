# DINQ 测试方案（离线可重复 + 在线 Smoke）

目标：
- **离线可重复（CI：workflow_dispatch 手动触发，触发后必跑）**：不依赖任何外部 API/网站/云 DB；结果稳定、可复现。
- **在线 Smoke（可选）**：需要密钥/网络，覆盖真实链路；允许更慢、更不稳定（默认不阻塞 CI）。

## 1) 测试分层

### A. Unit（离线）
- 只测纯逻辑/协议/任务调度/拼装（不发网络、不依赖数据库）。
- 入口：`tests/unit_tests/` 中的可重复用例（建议后续逐步把“脚本型 test_*.py”迁走）。

### B. Offline Integration（离线 + 本地依赖）
- 使用 `compose.yaml` 启动本地 Postgres（以及可选 MailHog），跑“路由/服务/DB”组合测试。
- 外部抓取/LLM/第三方 API 必须 **stub/mock**（fixture 或 patch），确保 100% 离线。

### C. Online Smoke（在线）
- 只跑最小用例（1～2 个请求），验证真实外部依赖可用（Scholar/GitHub/LinkedIn/邮件等）。
- 必须用 `skip if missing env`，避免在没有密钥的 CI 环境失败。

## 2) 本地一键（推荐）

说明：项目启动时会按优先级加载环境文件（不覆盖已存在的环境变量）：
`.env.<env>.local` → `.env.local` → `.env.<env>` → `.env`（建议把密钥放在 `.env.local`，已被 gitignore）。

### 2.1 启动本地依赖（Postgres + MailHog）
在 `DINQ/` 下：
```bash
docker compose up -d postgres
docker compose ps
```

可选：本地邮件收件箱（MailHog）：
```bash
docker compose up -d mailhog
```

### 2.2 运行离线 Unit
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -v -s tests/unit_tests -p "test_*.py"
```

### 2.3 运行离线集成（需要本地 Postgres）
说明：会设置 `DINQ_DB_URL` 指向本地 Postgres，并初始化表结构。

（后续脚本落地后）建议用：
```bash
./scripts/ci/test_offline_integration.sh
```

### 2.4 在线 Smoke（可选）
默认跳过，显式开启：
```bash
DINQ_RUN_ONLINE_SMOKE=true ./scripts/ci/test_online_smoke.sh
```

更重、更不稳定的 Scholar 链路（默认关闭）：
```bash
DINQ_RUN_ONLINE_SMOKE=true DINQ_SMOKE_SCHOLAR=true ./scripts/ci/test_online_smoke.sh
```

### 2.5 性能微基准（不联网）
```bash
PYTHONPATH=. python3 bench/sse_bench.py --events 2000
```

### 2.6 导出评分卡（推荐用于“量化对比”）
会生成 `reports/scorecard/<timestamp>-<sha>/scorecard.json`（以及各步骤 stdout/stderr 日志文件）。
```bash
make scorecard
```

### 2.7 查看 key 配置状态（脱敏）
```bash
make key-status
```

## 3) CI 建议（默认只跑离线）

- GitHub Actions 工作流全部为 `workflow_dispatch` 手动触发：
  - `ci.yml`：Unit（离线）+ Offline Integration（离线+compose）
  - `smoke.yml`：Online Smoke（在线，默认可用用例最小化；GitHub 需要 `GITHUB_TOKEN` 才会执行相关用例；Scholar 需要额外打开 `DINQ_SMOKE_SCHOLAR=true`）

## 4) 环境变量（建议）

仅示例，具体以 `.env.example` 为准：
- 完整密钥/配置清单见：`KEYS.md`
- `DINQ_DB_URL`: 指向本地 Postgres，例如 `postgresql+psycopg2://dinq:dinq@localhost:5432/dinq`
- `DINQ_AUTH_BYPASS`: 测试模式下绕过 `require_verified_user`（仅用于离线测试）
- `DINQ_EMAIL_BACKEND`: `resend|smtp|file|noop`（离线推荐 `file` 或 `smtp` + MailHog）
