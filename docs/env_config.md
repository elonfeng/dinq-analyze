# 环境变量配置指南（dinq-dev / Gateway 架构）

本文档以 **Gateway → dinq（分析服务）** 的新架构为准，汇总 dinq（Python）侧的核心环境变量。

> 前端不要直连 dinq（分析服务）。前端只调 Gateway：`https://api.dinq.me` 的 3 个核心接口。

---

## 0) .env 文件与加载规则

项目会在启动时加载 `.env.<env>`（例如 `.env.production`），并以系统环境变量优先。

生产部署（dinq-dev）推荐：
- `/root/dinq-dev/.env.production`（或拆成 `.env.production.local` 存敏感项）
- systemd 里显式设置：`DINQ_ENV=production`、`FLASK_ENV=production`

---

## 1) 必备配置（dinq-dev 运行所需）

### 1.1 环境

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_ENV` | `development/test/production` | `development` |
| `FLASK_ENV` | Flask 环境（部署时建议与 `DINQ_ENV` 一致） | `development` |

### 1.2 数据库（分析任务 job/events 持久化）

本项目采用“本地 SQLite 主存储 + 远程 Postgres 备份（可选）”的简化模型：
- **jobs DB（主）**：本机 SQLite（`jobs/job_cards/job_events/artifacts`）
- **cache DB（主）**：本机 SQLite（`analysis_*` 缓存表；默认单独文件，便于做磁盘淘汰）
- **backup DB（可选）**：远程 Postgres（仅异步 outbox 备份/冷启动读回；不在在线请求关键路径）

| 环境变量 | 说明 |
|---|---|
| `DINQ_JOBS_DB_URL` | jobs DB URL（仅支持 SQLite，例如 `sqlite:////data/dinq_jobs.sqlite3`） |
| `DINQ_CACHE_DB_URL` | cache DB URL（仅支持 SQLite，例如 `sqlite:////data/dinq_cache.sqlite3`） |
| `DINQ_DB_URL` | 统一本地 SQLite URL（向后兼容；同时作为 jobs/cache 的覆盖值） |
| `DINQ_BACKUP_DB_URL` | backup DB URL（可选；Postgres，用于 outbox 备份/读回） |
| `DATABASE_URL` | 若未设置 `DINQ_BACKUP_DB_URL`，并且 `DATABASE_URL` 是 Postgres，则会被视为 backup DB（兼容旧部署） |

连接池（仅对 Postgres backup 生效；本地主库 SQLite 不使用连接池）：

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_DB_POOL_SIZE` | 每进程连接池大小 | `10` |
| `DINQ_DB_MAX_OVERFLOW` | 允许溢出连接数 | `20` |
| `DINQ_DB_POOL_TIMEOUT` | 获取连接等待秒数 | `30` |
| `DINQ_DB_POOL_RECYCLE` | 连接回收秒数 | `3600` |
| `DINQ_DB_CONNECT_TIMEOUT` | DB connect_timeout（秒） | `30` |
| `DINQ_DB_APP_NAME` | Postgres application_name | `DINQ_App` |

---

## 1.3 SSE 流式推送加速（可选）

默认 SSE 通过数据库事件表 `job_events` 轮询回放（兼容多进程/多实例，支持断线续传）。

为了降低延迟（尤其是本地 inprocess 或多 worker 场景），可开启“推送背板”：

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_ANALYZE_SSE_BUS_MODE` | `auto/on/off`：是否启用进程内 SSE bus（同进程推送最快；`auto` 仅 `inprocess` 启用） | `auto` |
| `DINQ_ANALYZE_SSE_BACKPLANE` | `none/nats`：多进程/多实例背板（NATS 仅做 best-effort 推送唤醒；DB 仍是事实源） | `none` |
| `DINQ_NATS_URL` | NATS 地址（如 `nats://nats:4222`） | `nats://127.0.0.1:4222` |
| `DINQ_NATS_SUBJECT` | NATS subject | `dinq.job_events` |
| `DINQ_NATS_PUBLISH_MODE` | `auto/full/wakeup`：`auto` 小消息直推，大消息只发唤醒 | `auto` |
| `DINQ_NATS_MAX_EVENT_BYTES` | `auto` 模式下直推最大字节数（超出则降级为 wakeup） | `65536` |

> 注意：即使开启 NATS，SSE 仍会保留 DB fallback（防止背板消息丢失导致卡住）。

---

## 2) 鉴权模式（重要：Gateway 注入 Header）

dinq-dev 不再直接验证用户 JWT（Firebase 等），而是 **信任 Gateway 注入**：
- `X-User-ID`（必需）
- `X-User-Tier`（可选）

本地开发/CI（非 production）可临时打开绕过开关：

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_AUTH_BYPASS` | `true/false`（仅非 production 生效） | `false` |

> 安全要求：若取消 shared-secret（例如 `ANALYSIS_INTERNAL_TOKEN`），必须在网络层把 `:8080` 仅放行 Gateway 公网 IP。

---

## 3) Scholar 抓取/缓存（前端不需要传“调参”字段）

Scholar 的 crawl / cache 与“论文量策略”都是 **服务端策略**（环境变量控制）：

> 产品口径（10s 首屏）：`resource.scholar.page0` 默认只抓 **page0/少量论文** 以尽快产出 `profile/metrics/papers preview`；
> 同时会排队一个后台卡 `resource.scholar.full` 去抓更多页并 warm cache（不影响前端首屏）。

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `CRAWLBASE_API_TOKEN` / `CRAWLBASE_TOKEN` | Crawlbase token（任意一个即可） | - |
| `DINQ_SCHOLAR_USE_CRAWLBASE` | 是否启用 Crawlbase（未显式设置时，会根据 token 是否存在推断） | auto |
| `DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS` | 缓存最大天数（0–30） | `3` |
| `DINQ_SCHOLAR_MAX_PAPERS_PAGE0` | `resource.scholar.page0` 抓取的最大论文数（`0` 表示不限量；建议保持较小以保证首屏） | `30` |
| `DINQ_SCHOLAR_MAX_PAPERS_FULL` | 抓取/分析的最大论文数（`0` 表示不限量） | `500` |
| `DINQ_SCHOLAR_PAGE_CONCURRENCY` | Crawlbase 多页并行抓取并发（1–8，仅 Crawlbase 路径） | `3` |
| `DINQ_SCHOLAR_PAGE0_FETCH_TIMEOUT_SECONDS` | page0 抓取软超时（秒；用于“强保证首屏”的 timebox） | `10` |
| `DINQ_SCHOLAR_PAGE0_FETCH_MAX_RETRIES` | page0 抓取最大重试次数（0–2） | `1` |
| `DINQ_SCHOLAR_LEVEL_FAST_TIMEOUT_SECONDS` | `level` 卡 fast path 的 LLM 超时（秒；超时会回退并后台补齐） | `10` |
| `DINQ_SCHOLAR_PREVIEW_MAX_PAPERS` | `papers` 卡对外 preview 的最大论文条数（0–200；用于 `card.append` 增量输出） | `30` |
| `DINQ_SCHOLAR_PAPERS_MAX_ITEMS` | `papers` 卡最终输出中保留的 `items` 上限（0–1000；用于保护 payload 大小） | `200` |
| `DINQ_SCHOLAR_FETCH_DISK_CACHE_DIR` | Scholar 抓取 HTML 磁盘缓存目录（启用后可显著降低重复抓取/波动） | - |
| `DINQ_SCHOLAR_FETCH_DISK_CACHE_TTL_SECONDS` | Scholar 抓取磁盘缓存 TTL（秒） | `86400` |
| `DINQ_SCHOLAR_FIRST_AUTHOR_PAPERS_LIST_LIMIT` | `publication_stats.first_author_papers_list` 返回 TopK（0 表示不截断） | `50` |
| `DINQ_SCHOLAR_TOP_TIER_PUBLICATIONS_LIST_LIMIT` | `publication_stats.top_tier_publications` 返回 TopK（0 表示不截断） | `50` |
| `DINQ_SCHOLAR_TOP_COAUTHORS_LIMIT` | `coauthor_stats.top_coauthors` 返回 TopK | `20` |
| `DINQ_SCHOLAR_FINAL_CHECK_MOST_CITED_MAX_PAPERS` | most-cited 最终二次扫描阈值（大于该值跳过以提升性能；0 表示永远跳过） | `2000` |

---

## 4) GitHub（可选）

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `GITHUB_TOKEN` | GitHub API token（用于 GitHub 资源抓取与 freeform 解析） | - |
| `DINQ_GITHUB_PROFILE_TIMEOUT_SECONDS` | `resource.github.profile` GraphQL profile 软超时（秒；超时会降级到 REST/最小 identity） | `8` |
| `DINQ_GITHUB_PROFILE_REST_TIMEOUT_SECONDS` | `resource.github.profile` REST profile 超时（秒） | `6` |
| `DINQ_GITHUB_PREVIEW_PR_REPOS_YEARS` | `resource.github.preview` 统计 top_projects 的年数窗口（越小越快） | `3` |
| `DINQ_GITHUB_PREVIEW_TIMEOUT_SECONDS` | `resource.github.preview` 总预算超时（秒） | `8` |
| `DINQ_GITHUB_FULL_PR_REPOS_YEARS` | `resource.github.data` 的 top_projects 年数窗口（更全口径，但可能更慢） | `5` |
| `DINQ_GITHUB_PR_REPOS_TIMEOUT_SECONDS` | `resource.github.data` 的 pr_repos 软超时（秒；超时继续跑其他数据） | `8` |
| `DINQ_GITHUB_ENRICH_FAST_SKIP_LLM` | `resource.github.enrich` Fast path 直接跳过 LLM（强保证不被 LLM 长尾阻塞；会后台 refresh 写跨 job cache） | `0` |
| `DINQ_GITHUB_ENRICH_FAST_TIMEOUT_SECONDS` | `resource.github.enrich` Fast path 的 LLM 软超时（秒；超时走启发式 fallback） | `10` |
| `DINQ_GITHUB_ENRICH_BACKGROUND_TIMEOUT_SECONDS` | GitHub enrich 的后台 refresh LLM 超时（秒；不阻塞 job） | `60` |
| `DINQ_GITHUB_ENRICH_PR_MAX_CANDIDATES_FAST` | enrich Fast path 喂给 LLM 的 PR 候选条数（TopN；越小越快） | `10` |
| `DINQ_GITHUB_ENRICH_PR_MAX_CANDIDATES_BG` | enrich 后台 refresh 喂给 LLM 的 PR 候选条数（TopN；越大越准但更慢） | `30` |

---

## 5) 分析调度器并发（服务端配置，不属于请求参数）

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_ANALYZE_SCHEDULER_MAX_WORKERS` | DB-backed 卡片调度器线程池大小（影响并发吞吐） | `4` |
| `DINQ_ANALYZE_CONCURRENCY_GROUP_LIMITS` | 分组并发预算（逗号分隔，如 `llm=4,github_api=8,crawlbase=2,apify=1`） | 内置默认：`llm` 会随 `max_workers` 自动上限（默认最多 4） |

## 5.1) GitHub `best_pr` timebox（10s 体验关键）

为了避免 GitHub `repos` 卡因 LLM 长尾（`ai_best_pr`）拖慢整体体验，后端支持“10s 预算内超时降级 + 后台补齐”：

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_GITHUB_BEST_PR_SOFT_TIMEOUT_SECONDS` | 前台 `repos` 卡里 best_pr 的 LLM 软超时（秒）；超时立即启发式降级 | `10` |
| `DINQ_GITHUB_BEST_PR_MAX_CANDIDATES` | 前台喂给 LLM 的 PR 候选条数（TopN；越小越快） | `10` |
| `DINQ_GITHUB_BEST_PR_BACKGROUND_TIMEOUT_SECONDS` | 后台补齐 best_pr 的 LLM 超时（秒） | `60` |
| `DINQ_GITHUB_BEST_PR_BG_MAX_CANDIDATES` | 后台补齐喂给 LLM 的 PR 候选条数 | `50` |

> 说明：发生前台超时后，系统会排队一个内部卡 `resource.github.best_pr`，完成后会用新的 `card.completed` 覆盖更新 `repos.most_valuable_pull_request`。

---

## 5.2) LLM 路由与模型选择（OpenRouter / Groq）

LLM 选型是“部署策略”，默认 speed-first，并支持按任务覆盖/多路由：

必备 key：
- OpenRouter：`OPENROUTER_API_KEY`（或旧名 `OPENROUTER_KEY` / `GENERIC_OPENROUTER_API_KEY`）
- （可选）Groq：`GROQ_API_KEY`（或旧名 `GROQ_KEY`）

| 环境变量 | 说明 |
|---|---|
| `DINQ_LLM_MODEL_FAST` | fast profile 的默认模型 |
| `DINQ_LLM_MODEL_BALANCED` | balanced profile 的默认模型 |
| `DINQ_LLM_TASK_MODEL_<TASK>` | 覆盖某个任务的“单路由”（支持 `openrouter:<model>` / `groq:<model>`；不带前缀则默认 OpenRouter） |
| `DINQ_LLM_TASK_ROUTES_<TASK>` | 覆盖某个任务的“多路由”（逗号分隔，如 `groq:<model>,openrouter:<model>`） |
| `DINQ_LLM_TASK_POLICY_<TASK>` | 多路由策略：`single` / `fallback` / `hedge`（默认：JSON 任务用 hedge，其它用 fallback） |
| `DINQ_LLM_HEDGE_DELAY_MS` | hedge 策略的全局延迟（毫秒；到点仍未拿到可用结果才触发 secondary） |
| `DINQ_LLM_TASK_HEDGE_DELAY_MS_<TASK>` | 覆盖单个任务的 hedge delay（毫秒） |

任务 key 的规范化规则：将非字母数字替换为 `_` 并大写（例如 `juris.salary_eval` → `DINQ_LLM_TASK_MODEL_JURIS_SALARY_EVAL`）。

## 5.3) freeform 预解析（可选）

当请求带 `options.freeform=true` 且输入较模糊时，服务端会尝试返回候选实体（不创建 job）。

当前支持返回候选列表的 `source`：`scholar`、`github`、`linkedin`。

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_ANALYZE_FREEFORM_MAX_CANDIDATES` | 返回候选数量上限（1–10） | `5` |

---

## 5.4) 分析缓存与增量刷新（SWR，可选）

dinq 会对「同一 subject（人/账号/URL）」的 `full_report` 做跨 job 复用缓存，并支持 **stale-while-revalidate**：
- cache 仍在 TTL 内：直接复用（更快、更省成本）
- cache 过期：可先通过 `card.prefill` 预填充旧结果（UI 预览），同时后台重新计算并用 `card.completed` 覆盖为最终结果

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_ANALYZE_PIPELINE_VERSION` | 缓存版本号（当分析逻辑有破坏性变更时手动 bump，用于整体“清缓存”） | `v1` |
| `DINQ_ANALYZE_CACHE_TTL_SECONDS` | `full_report` 缓存 TTL（秒；全局默认） | `86400` |
| `DINQ_ANALYZE_CACHE_TTL_SECONDS_<SOURCE>` | 覆盖单个 source 的 TTL（如 `..._GITHUB`） | - |
| `DINQ_ANALYZE_CACHE_MAX_STALE_SECONDS` | TTL 过期后，允许“指纹未变化则复用并延长 TTL”的最大过期窗口（秒） | `604800` |
| `DINQ_ANALYZE_CACHE_MAX_STALE_SECONDS_<SOURCE>` | 覆盖单个 source 的 max-stale | - |
| `DINQ_ANALYZE_PREFILL_MAX_AGE_SECONDS` | 允许发出 `card.prefill` 的最大 cache 年龄（秒；0 表示关闭 prefill） | `604800` |
| `DINQ_ANALYZE_PREFILL_MAX_AGE_SECONDS_<SOURCE>` | 覆盖单个 source 的 prefill max age | - |
| `DINQ_ANALYZE_REFRESH_LOCK_TTL_SECONDS` | 全局 refresh 去重锁的超时（秒；防止 worker 崩溃导致“running”卡死） | `900` |

---

## 5.5) 后台 refresh（不占用 job_cards）

用于“Fast fallback -> 后台补齐 -> 下次命中缓存”的 refresh 线程池：

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_BG_REFRESH_ENABLED` | 是否启用后台 refresh（true/false） | `true` |
| `DINQ_BG_REFRESH_MAX_WORKERS` | 后台 refresh 线程池并发（1–16） | `2` |

---

## 5.6) LLM HTTP 客户端（连接复用 / 429/5xx 保护）

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_OPENROUTER_BASE_URL` | OpenRouter base url（高级；默认无需设置） | `https://openrouter.ai/api/v1` |
| `DINQ_OPENROUTER_APP_TITLE` | OpenRouter `X-Title`（可选，便于统计/排查） | - |
| `DINQ_GROQ_BASE_URL` | Groq base url（高级；默认无需设置） | `https://api.groq.com/openai/v1` |
| `DINQ_LLM_HTTP_POOL_MAXSIZE` | requests 连接池大小（影响并发连接复用） | `32` |
| `DINQ_LLM_HTTP_MAX_ATTEMPTS` | 429/5xx/timeout 时的最大尝试次数（1–5；建议 Fast path 维持 1） | `1` |
| `DINQ_LLM_CIRCUIT_BREAKER_ENABLED` | 是否启用熔断（true/false） | `true` |
| `DINQ_LLM_CIRCUIT_BREAKER_FAIL_THRESHOLD` | 连续失败次数阈值（>= 后进入熔断窗口） | `5` |
| `DINQ_LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS` | 熔断窗口秒数（窗口内直接快速失败） | `20` |
| `DINQ_LLM_OPENROUTER_MAX_CONCURRENCY` | OpenRouter 并发上限（0 表示不限制） | `0` |
| `DINQ_LLM_GROQ_MAX_CONCURRENCY` | Groq 并发上限（0 表示不限制） | `0` |
| `DINQ_LLM_HEDGE_MAX_WORKERS` | hedge 内部线程池上限（1–64） | `8` |
| `DINQ_LLM_LOG_EACH_REQUEST` | 是否记录每次 LLM 请求的结构化日志（默认只在慢/异常时记录） | `false` |
| `DINQ_ANALYZE_SSE_BATCH_SIZE` | SSE 续传拉取 job_events 的每次 DB 批量上限（1–5000） | `500` |

说明：
- 内置默认 TTL（不设置 env 时生效；仍可用 `..._TTL_SECONDS_<SOURCE>` 覆盖）：SCHOLAR=3d、LINKEDIN=7d、GITHUB=6h、其余=24h。
- “指纹（fingerprint）增量刷新”当前实现于：
  - GitHub：公开 events / profile updated_at
  - Scholar：抓取 1 个 profile 页计算 citations/h-index/近三年 citations 指纹
- 前端若要强制重新计算，可在请求里加：`{ "options": { "force_refresh": true } }`（会跳过缓存读取与 prefill；但仍会写入/更新缓存）。

---

## 5.5) Realtime（DB-only）

Analyze 的流式事件（SSE）与快照恢复均基于数据库：
- SSE：轮询 `job_events`（按 `seq` 递增回放）
- 快照：读取 `job_cards.output`（包含 `card.delta/card.append` 写入的增量结果）

---

## 6) API 域名前缀（用于生成 URL）

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `DINQ_API_DOMAIN` | 生成报告/资源 URL 的域名前缀 | 根据 `DINQ_ENV` 推断 |

未设置时：
- development：`http://127.0.0.1:5001`
- test：`https://test-api.dinq.ai`
- production：`https://api.dinq.me`（当前部署）

---

## 7) 示例（仅示意，不要把密钥提交到仓库）

`.env.production`（示例）：

```bash
DINQ_ENV=production
FLASK_ENV=production
DINQ_API_DOMAIN=https://api.dinq.me
DINQ_DB_URL=postgresql://USER:PASSWORD@127.0.0.1:5432/dinq
DINQ_DB_POOL_SIZE=5
DINQ_DB_MAX_OVERFLOW=5
DINQ_ANALYZE_SCHEDULER_MAX_WORKERS=4
DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS=3
DINQ_SCHOLAR_USE_CRAWLBASE=true
DINQ_SCHOLAR_MAX_PAPERS_PAGE0=30
DINQ_SCHOLAR_MAX_PAPERS_FULL=500
DINQ_SCHOLAR_PAGE_CONCURRENCY=3
```

注意：
- `.env*` 应加入 `.gitignore`，避免提交敏感信息
- 生产环境建议使用 systemd 环境变量或机密管理（同时可保留 `.env.production.local`）
