# Unified Analyze API

## Overview
The unified analyze API is exposed to the frontend via **Gateway** and executed by the **analysis service** (this repo).

- **Gateway (public):** `POST /api/v1/analyze` + `GET /api/v1/analyze/jobs/<job_id>` + `GET /api/v1/analyze/jobs/<job_id>/stream`
- **Analysis upstream (internal / local debug):** `POST /api/analyze` + `GET /api/analyze/jobs/<job_id>` + `GET /api/analyze/jobs/<job_id>/stream`

It supports **async job creation** (then SSE replay via `GET .../stream`) and **sync JSON** (debug) with card-level outputs.

前端对接与卡片字段（scholar/github/linkedin）详见：
- `docs/frontend/ANALYZE_CARDS.md`

## POST /api/v1/analyze

### Request

> `cards` 可不传；不传或传 `[]` 时默认跑该 `source` 的全部卡片。

```json
{
  "source": "scholar|github|linkedin|twitter|openreview|huggingface|youtube",
  "mode": "async|sync",
  "input": {},
  "cards": ["profile", "metrics", "summary"],
  "options": {}
}
```

#### 参数说明（简版）

- `source`：必填
- `mode`：可选，默认 `async`
- `input`：按 source 不同而不同（见下方）
- `cards`：可选；只做结果裁剪/加速（后端会自动补依赖）
- `options`：可选；支持 `freeform=true`（模糊输入返回候选实体，需用户确认）

#### Header
- Frontend -> Gateway:
  - `Authorization: Bearer <gateway_jwt>`
  - 可选：`Idempotency-Key: <string>`
- Gateway -> Analysis upstream:
  - `X-User-ID: <string>`（必需）
  - `X-User-Tier: <string>`（可选）
  - 说明：分析服务不再验证 Firebase/JWT；仅信任 gateway 注入的用户上下文。

#### input（按 source）

> 推荐统一使用：`input.content`（跨 source 一致）。历史字段仍兼容但不建议新业务依赖。

- `scholar`：`content`（Scholar ID / Scholar URL / 人名）
- `github`：`content`（GitHub login / profile URL / 不规范内容会尝试搜索解析）
- `linkedin`：`content`（LinkedIn URL / 人名）
- `twitter`：`content`（username 或 profile URL，可带 `@`）
- `openreview`：`content`（OpenReview profile id 或 email）
- `huggingface`：`content`（HuggingFace username 或 profile URL）
- `youtube`：`content`（channel_id / channel URL / @handle / 名称）

#### cards（按 source）

- `scholar`：`profile/metrics/papers/citations/coauthors/role_model/news/level/summary`
- `github`：`profile/activity/repos/role_model/roast/summary`
- `linkedin`：`profile/skills/career/role_model/money/roast/summary`
- `twitter`：`profile/stats/network/summary`
- `openreview`：`profile/papers/summary`
- `huggingface`：`profile/summary`
- `youtube`：`profile/summary`

卡片字段（每张卡的 `output.data`/`output.stream` 结构）详见：
- `docs/frontend/ANALYZE_CARDS.md`

### SSE（GET /stream）
（不再从 POST 返回 SSE）创建任务后，请使用 `GET /api/v1/analyze/jobs/<job_id>/stream?after=<seq>` 订阅 SSE。
服务端在看到 `job.completed` 事件后会自动关闭连接（统一终止信号）。
`job.completed.payload.status` 可能为：`completed | partial | failed`。
`job.failed` 仍可能被发出用于诊断/兼容，但 **不会** 作为 SSE 终止条件。

### Response (mode=async)
```json
{
  "success": true,
  "job_id": "<job_id>",
  "status": "queued|running|completed|partial|failed",
  "cache_hit": false,
  "cache_stale": false,
  "refresh_in_progress": false,
  "idempotent_replay": false
}
```

补充：
- 若服务端判定输入模糊且需要用户确认，会返回 `needs_confirmation=true` + `candidates`（不创建 job）。

### Response (mode=sync)
```json
{
  "success": true,
  "job_id": "<job_id>",
  "status": "completed|partial|failed",
  "cards": {
    "profile": { "data": {}, "stream": {} },
    "metrics": { "data": {}, "stream": {} }
  },
  "errors": []
}
```

## GET /api/v1/analyze/jobs/<job_id>
Returns job status and completed cards.

## GET /api/v1/analyze/jobs/<job_id>/stream?after=<seq>
SSE replay of events (supports resume).

## SSE Event Types
- `job.started`
- `job.completed`
- `job.failed`
- `card.started`
- `card.progress`（阶段进度；常用于内部 resource 卡，也会用于耗时子步骤提示）
- `card.append`（结构化列表增量；用于 preview 列表边抓边出）
- `card.delta`
- `card.completed`
- `card.failed`
- `ping`（keepalive）

Each event payload includes `job_id` and `seq`.

### `card.append` payload (schema, best-effort)
```json
{
  "job_id": "<job_id>",
  "seq": 123,
  "card": "papers|repos|...",
  "path": "items|top_projects|...",
  "items": [],
  "dedup_key": "id",
  "cursor": {},
  "partial": true
}
```

## Legacy endpoints
This doc only covers the unified analyze entrypoint. Legacy APIs are intentionally not documented here.
