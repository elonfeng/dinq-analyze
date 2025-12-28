# DINQ Key / 密钥清单（统一用 env 管理）

原则：
- **不要把真实密钥提交到 Git**（包括 `.env.example/.env.production` 这类模板文件）。
- 本地开发：把密钥放在 `DINQ/.env.local`（已在 `.gitignore` 中忽略）或直接 `export` 到 shell。
- CI：用 GitHub Actions Secrets 注入（本仓库工作流已改为 `workflow_dispatch` 手动触发）。
- 生产：由部署平台注入环境变量；如需文件，优先用 `.env.production.local`（同样被 gitignore）。

## 1) 必选/常用

- `DINQ_ENV`：`development|test|production`，影响加载的 `.env.*` 文件与部分默认行为。
- `DINQ_API_DOMAIN`：用于生成报告 URL 的域名部分（例如 `http://localhost:5001` / `https://api.dinq.ai`）。
- `DINQ_DB_URL`：数据库连接串（离线集成测试会指向 compose 的 Postgres）。

## 2) Scholar（Google Scholar 抓取/分析）

### 抓取能力（强烈建议配齐）
- `CRAWLBASE_API_TOKEN`：Crawlbase token（更稳定、封禁风险更低）。
  - 使用处：`server/services/scholar/*`、`server/api/scholar/*`、`server/api/scholar_pk/*`
  - 兼容：历史上也用过 `CRAWLBASE_TOKEN`，建议统一迁到 `CRAWLBASE_API_TOKEN`。

### 可选抓取/补全
- `FIRECRAWL_API_KEY`：Firecrawl key（用于部分补全抓取；缺失时应自动降级/跳过）。

### 调度/缓存（不属于“密钥”，但强相关）
- `DINQ_SCHOLAR_FETCH_MAX_INFLIGHT_PER_DOMAIN`：同域最大并发（默认 `1`，更稳、更不易触发风控）。
- `DINQ_SCHOLAR_FETCH_DISK_CACHE_DIR`：抓取磁盘缓存目录（强烈建议开启，显著减少请求数）。
- `DINQ_SCHOLAR_FETCH_DISK_CACHE_TTL_SECONDS`：磁盘缓存 TTL。
- `DINQ_SCHOLAR_FETCH_QUOTA_MAX_PER_DAY` / `DINQ_SCHOLAR_FETCH_QUOTA_STATE_PATH`：按 user+domain 的日配额（可选）。
- `DINQ_SCHOLAR_MAX_PAPERS_FULL`：抓取论文上限（影响分页/请求数；`0` 表示不限量）。

## 3) LLM（生成/总结/评估）

- `OPENROUTER_API_KEY`：OpenRouter key（研究者评价、论文总结、部分模板渲染等）。
- `GENERIC_OPENROUTER_API_KEY`：通用 OpenRouter key（被 `server/utils/ai_tools.py` 使用；可与上面同值）。
- `KIMI_API_KEY`：Moonshot/Kimi key（PK roast、部分 analyzer 可能用到）。
- `OPENROUTER_MODEL`：部分场景允许覆盖默认模型（可选）。

## 4) GitHub Analyzer

- `GITHUB_TOKEN`：用于 GitHub API（`/api/github/health`、`/api/github/analyze-stream`）。

## 5) LinkedIn / Twitter / YouTube（可选）

- `SCRAPINGDOG_API_KEY`：LinkedIn 相关抓取。
- `APIFY_API_KEY`：部分社媒抓取（LinkedIn/Twitter）。
- `TWITTER_*`（`TWITTER_API_KEY/TWITTER_API_SECRET/...`）：作者/推特相关接口。
- `YOUTUBE_API_KEY`：YouTube Analyzer。

## 6) 邮件（Verification / Outbox）

- `DINQ_EMAIL_BACKEND`：`resend|smtp|file|noop`
- `RESEND_API_KEY`：当 backend=`resend` 才需要。
- `DINQ_SMTP_HOST` / `DINQ_SMTP_PORT`：当 backend=`smtp` 才需要（离线可配 MailHog）。
- `DINQ_TEST_EMAIL_OUTBOX_PATH`：当 backend=`file` 时写入位置（离线测试推荐）。

## 7) Auth / Firebase

- `FIREBASE_SERVICE_ACCOUNT_PATH`：Firebase service account JSON 路径（不要提交到仓库；放 `.env.local` 或 secret volume）。
- `FIREBASE_SKIP_AUTH_IN_DEV`：仅开发辅助（生产不要开启）。
- `DINQ_AUTH_BYPASS`：测试/CI 用于绕过 verified-user（生产不要开启）。

## 8) Observability

- `SENTRY_DSN` + `SENTRY_*`：Sentry。
- `AXIOM_ENABLED` / `AXIOM_TOKEN` / `AXIOM_DATASET`：Axiom（建议默认关闭，避免离线/CI 外联）。

## 9) 在线 Smoke 怎么“全量跑起来”

本地：
- 把真实 keys 放 `DINQ/.env.local`
- 然后跑：
  - `DINQ_RUN_ONLINE_SMOKE=true ./scripts/ci/test_online_smoke.sh`
  - Scholar 链路（更不稳定）额外加：`DINQ_SMOKE_SCHOLAR=true`

CI（手动触发）：
- 在 GitHub 仓库 Settings → Secrets 配齐对应 keys，然后触发 `.github/workflows/smoke.yml`。
