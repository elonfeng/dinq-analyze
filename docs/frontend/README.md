# 前端对接手册

## Base URL（当前部署）
- 生产（Gateway）：`https://api.dinq.me`
- 内部上游（分析服务 dinq-dev）：`http://74.48.107.93:8080`（仅供 gateway 调用；前端不要直连）

## 0) 前端接入逻辑（推荐实现）

核心原则：
- 前端只渲染业务卡：`internal=false`；`resource.*` / `full_report` 等内部卡只做进度展示（可选）。
- **快照是可恢复的单一真相**：`GET /api/v1/analyze/jobs/<id>` 会返回每张卡的 `output={data,stream}`，并包含已累计的 `output.stream`（断线/刷新后可直接恢复 UI）。
- SSE 只负责“实时增量”，断线后通过 `after=<last_seq>` 无损续传；收到 `job.completed/job.failed` 后结束。

推荐前端流程：
1) `POST /api/v1/analyze`（默认 `mode=async`）
   - 若返回 `needs_confirmation=true`：展示 `candidates`，用户确认后用选中的 `candidate.input` 再发一次 create。
   - 若返回 `status=completed` 且包含 `cards`：表示命中最终结果缓存（直出），可直接渲染并跳过快照/SSE。
   - 若返回 `async_create=true`：表示后端已先返回 `job_id`，DB job 创建在后台进行；SSE `/stream` 会短暂等待 job 出现（前端也可对快照接口做重试/backoff）。
   - `subject_key` 可直接用于前端路由（唯一标识），也可在刷新/直链打开页面时作为 `input.content` 重新发起 create（后端会自动识别并解析）。
2) 进入结果页后，先 `GET /api/v1/analyze/jobs/<job_id>` 初始化 UI（包含 `stream_spec`，用于“零硬编码”分段渲染）。
3) 打开 SSE：`GET /api/v1/analyze/jobs/<job_id>/stream?after=<snapshot.last_seq>`
4) 消费事件并更新 UI（建议前端维护 `cards[card].output={data,stream}`）：
   - `card.started`：可用 `payload.stream` 或快照中的 `stream_spec` 决定渲染形态。
   - `card.prefill`：把 `payload.data` + `payload.stream` 合并进卡片（显示“预览态/缓存 as_of”，等待最终覆盖）。
   - `card.append`：结构化列表增量（papers/repo previews）。把 `items` 追加到 `output.data[path]`（按 `dedup_key` 去重），并更新 `cursor/partial`。
   - `card.delta`：按 `field/section/format` 把 `delta` 追加到 `output.stream[field].sections[section]`。
     - 注：后端为控成本/控写入，会按 chunk 批量 flush（不是“一个字一个字一事件”）；若要打字机效果建议前端自行按字符动画渲染。
   - `card.completed`：用 `payload.data` 覆盖 `output.data`（保留/合并 `output.stream`），状态置为 completed。
   - `job.completed/job.failed`：服务端严格只发一次；收到后停止 SSE。

## 1) 统一入口（推荐）
### POST /api/v1/analyze（通过 Gateway）
#### 最小可用请求（推荐先用 sync 验链路）
```json
{
  "source": "scholar",
  "mode": "sync",
  "input": { "content": "Y-ql3zMAAAAJ" }
}
```

#### 请求参数说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `source` | string | ✅ | - | 分析类型：`scholar/github/linkedin/twitter/openreview/huggingface/youtube` |
| `mode` | string | ❌ | `async` | `async` 只创建 job 并返回 JSON（推荐）；`sync` 直接返回结果 JSON（调试用） |
| `input` | object | ❌ | `{}` | 各 `source` 的输入参数（见下方“各 source 输入”） |
| `cards` | string[] | ❌ | `null` | 可不传/传空数组：默认跑该 `source` 的全量卡片（见下方“可用 cards”） |
| `options` | object | ❌ | `{}` | 可选：`force_refresh=true`（跳过缓存读取/预填充，强制重算；但仍会写入/更新缓存）；`allow_ambiguous=true`（允许直接用人名/模糊输入创建 job，不推荐，会影响缓存与准确性） |

#### 完整请求（示例）
```json
{
  "source": "scholar" | "github" | "linkedin" | "twitter" | "openreview" | "huggingface" | "youtube",
  "mode": "async" | "sync",
  "input": { "scholar_id": "..." },
  "cards": ["profile", "metrics", "summary"],
  "options": {}
}
```

#### Header
- `Authorization: Bearer <gateway_jwt>`
- 可选：`Idempotency-Key: <string>`（同一请求重试不产生重复 job）

### 结果（async）
```json
{
  "success": true,
  "job_id": "...",
  "subject_key": "...",            // 建议用它做页面唯一标识（/analyze/<source>/<subject_key>）
  "status": "queued|running|completed|partial|failed",
  "cache_hit": false,             // 可选：true 表示服务端已直接用缓存完成该 job
  "cache_stale": false,           // 可选：true 表示命中的是“过期但可用”的缓存（SWR）
  "refresh_in_progress": false,   // 可选：true 表示已有其他 job 在后台刷新（当前 job 直接用 stale cache 完成）
  "async_create": false,          // 可选：true 表示 create 先返回 job_id，DB job 在后台创建（低延迟）
  "cards": {                      // 可选：仅在 `status=completed` 的缓存直出时返回
    "profile": { "data": { }, "stream": { } },
    "summary": { "data": { }, "stream": { } }
  },
  "idempotent_replay": false
}
```

### 结果（sync）
```json
{
  "success": true,
  "job_id": "...",
  "status": "completed",
  "cards": {
    "profile": { "data": { }, "stream": { } },
    "summary": { "data": { }, "stream": { } }
  },
  "errors": []
}
```

### SSE（统一走 GET /stream）
- SSE 只走：`GET /api/v1/analyze/jobs/<id>/stream?after=<seq>`
- 服务端在发出 `job.completed/job.failed` 后会自动结束连接（前端也可以在 UI 切换时 `abort()`）
- 若前端需要“零硬编码”的分段渲染：快照接口 `GET /api/v1/analyze/jobs/<id>` 会返回每张卡的 `stream_spec`（field/format/sections）。

## 1.1) 各 source 输入（input）怎么填

> 说明：`input` 本身不是“必填字段”，但每个 source 对 `input` 内部字段有要求；缺字段会返回 400/500。

- `scholar`
  - 推荐：`input.content`
    - 可传：Scholar ID（如 `Y-ql3zMAAAAJ`）/ Scholar 主页 URL / 人名/描述（会触发候选确认，选定后再分析）
  - 说明：抓取与缓存策略（Crawlbase token、cache age 等）由服务端环境变量控制，前端不需要传入
- `github`
  - 推荐：`input.content`
    - 可传：GitHub login / profile URL / 人名/描述（会触发候选确认，选定 login 后再分析）
- `linkedin`
  - 推荐：`input.content`（建议传 LinkedIn URL；若传人名/描述会触发候选确认，选定 profile URL 后再分析）
  - 可选别名：`input.name` / `input.person_name`
- `twitter`
  - 推荐：`input.content`（用户名或 profile URL；可带 `@`）
- `openreview`
  - 推荐：`input.content`（OpenReview profile id 或 email）
- `huggingface`
  - 推荐：`input.content`（HuggingFace username 或 profile URL）
- `youtube`
  - 推荐：`input.content`（channel_id / channel URL / @handle / 名称）

## 1.2) cards 怎么用（可不传）

- `cards` **可以不传**（或传 `[]`），后端会按 `source` 使用默认卡片集合。
- 若你只想要部分结果（更快/更省 LLM），传子集即可；后端会自动补齐依赖（不同 source 可能依赖内部 `resource.*` 或 `full_report`）。

可用 cards（按 source）：

- `scholar`：`profile/metrics/papers/citations/coauthors/role_model/news/level/summary`
- `github`：`profile/activity/repos/role_model/roast/summary`
- `linkedin`：`profile/skills/career/role_model/money/roast/summary`
- `twitter`：`profile/stats/network/summary`
- `openreview`：`profile/papers/summary`
- `huggingface`：`profile/summary`
- `youtube`：`profile/summary`

## 1.2.1) 卡片依赖 DAG（执行顺序）

三大常用 source（`scholar/github/linkedin`）后端使用 DAG 拆分执行（会出现内部 `resource.*` 卡片，用于更快出结果/降低成本），详见：

- `docs/frontend/ANALYZE_DAG.md`

## 1.3) 卡片字段格式（详版）

各 source 的卡片字段、示例、SSE 事件说明详见：

- `docs/frontend/ANALYZE_CARDS.md`

## 1.4) 候选确认（模糊输入→解析成唯一标识）

为了保证 **缓存键基于唯一标识**（避免同名错人/错缓存），对 `scholar/github/linkedin`：
- 当 `input.content` 不是稳定的 `ID/login/URL` 时，服务端会先尝试解析：
  - 若只解析出 **1 个**可靠候选：服务端会自动把 `input.content` 规范化为该候选的 `ID/login/URL` 并继续创建 job（会比纯 ID/URL 输入更慢一些）
  - 若解析出 **0 个或多个**候选：服务端会返回 `needs_confirmation=true`（不会创建 job，不会返回 `job_id`）
- 前端在 `needs_confirmation=true` 时：展示 `candidates` 让用户选一个，再用选中的 `candidate.input.content` 重新调用一次 `POST /api/v1/analyze`

当前支持返回候选列表的 `source`：
- `scholar`
- `github`
- `linkedin`

其他 source 目前可能返回 `needs_confirmation=true` 但 `candidates=[]`（表示服务端无法给出可靠候选），前端应提示用户输入更明确的 URL/ID/用户名。

若服务端判定输入模糊，会 **不创建 job**，直接返回：

```json
{
  "success": true,
  "needs_confirmation": true,
  "candidates": [
    { "label": "...", "input": { "content": "..." }, "meta": {} }
  ]
}
```

前端应展示 `candidates` 让用户选一个，然后把选中的 `candidate.input` 作为新的 `input` 再调用一次 `POST /api/v1/analyze`。

## 2) SSE 事件协议
统一事件字段：
```json
{
  "source": "analysis",
  "event_type": "card.delta",
  "message": "",
  "payload": {
    "job_id": "...",
    "seq": 12,
    "card": "summary",
    "field": "critical_evaluation",
    "section": "overview",
    "format": "markdown",
    "delta": "..."
  }
}
```

常见事件类型：
- `job.started`
- `card.started`
- `card.prefill`（可选：缓存预填充，用于“先显示旧结果再后台刷新”）
- `card.progress`（可选：后端阶段进度提示；常用于内部 resource 卡）
- `card.append`（可选：结构化列表增量，preview 边抓边出）
- `card.delta`
- `card.completed`
- `card.failed`
- `job.completed` / `job.failed`
- `ping`

## 3) 断线续传
- 保存最后 `seq`
- 断线重连调用：
  - `GET /api/v1/analyze/jobs/<id>/stream?after=<seq>`

## 3.1) 前端 JS 参考（fetch 读 SSE，支持 Authorization header）

浏览器原生 `EventSource` **无法设置请求头**，建议用 `fetch()` 读 `text/event-stream`：

```ts
export async function streamSSE(url: string, token: string, onEvent: (evt: any) => void, signal?: AbortSignal) {
  const resp = await fetch(url, {
    method: "GET",
    headers: { Authorization: token.startsWith("Bearer ") ? token : `Bearer ${token}`, Accept: "text/event-stream" },
    signal,
  });
  if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    while (true) {
      const idx = buffer.indexOf("\\n\\n");
      if (idx === -1) break;
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of frame.split("\\n")) {
        const t = line.trim();
        if (!t.startsWith("data:")) continue;
        const jsonText = t.slice("data:".length).trim();
        if (!jsonText) continue;
        try { onEvent(JSON.parse(jsonText)); } catch {}
      }
    }
  }
}
```

## 4) 卡片渲染建议
- `card.prefill`：可先展示“缓存命中”的预览态（建议标注 `as_of`），后续用 `card.completed` 覆盖为最终内容
- `card.progress`：可用于进度条/步骤提示（`payload.card` 可能是内部 `resource.*`，前端可忽略或仅做 loading 文案）
- `card.delta`：逐段流式渲染
- `card.completed`：覆盖/收敛为最终内容
- `card.failed`：显示错误但不中断全局

## 4.1) 本地联调工具（已放到仓库）

- CLI smoke：`scripts/api_tests/test_analyze_gateway.sh`
  - `TOKEN=<jwt> ./scripts/api_tests/test_analyze_gateway.sh smoke`
- 浏览器 Playground：`examples/analyze_gateway_playground.html`
  - `cd examples && python3 -m http.server 5173`
  - 打开 `http://localhost:5173/analyze_gateway_playground.html`

## 5) 旧接口（兼容）
- `/api/stream`：旧 Scholar SSE
- `/api/scholar-pk`：PK 流式
- `/api/github/analyze-stream`：GitHub SSE

说明：以上为历史存量页面接口，新产品请统一切换到 Gateway 的 `/api/v1/analyze`（以及对应的 jobs/stream）。
