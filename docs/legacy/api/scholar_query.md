# 单个学者查询 API（Scholar Stream / SSE）

该接口用于查询单个学者的学术信息，支持通过姓名或 Google Scholar ID / URL 查询；响应为 SSE 流式输出。

## 接口信息

- **URL**: `{API_BASE_URL}/api/stream`
- **方法**: `POST`（推荐）/ `GET`（历史兼容/调试）
- **响应格式**: Server-Sent Events (SSE)，仅输出 `data: {json}\n\n`
- **认证**: 通常需要请求头 `Userid`（生产场景建议走真实认证；本地测试可开启 bypass）

## 请求参数

### POST JSON Body（推荐）

```json
{
  "query": "Y-ql3zMAAAAJ"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `query` | string | 是 | 学者姓名、Google Scholar ID 或 URL |

说明：
- 该接口不再支持“精简模式/简化模式”参数（`simplify`/`simplyfy_flag` 已移除）
- 该接口不再支持旧版 `async_enrich/background_enrich` 参数（已移除）

### GET Query Params（兼容）

`/api/stream?query=...`（注意：GET 无法带自定义请求头，生产通常不可用）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `query` | string | 是 | 同上 |

## 输入格式说明

`query` 支持：
1) **Google Scholar ID**：`Y-ql3zMAAAAJ`（最准确）
2) **Google Scholar URL**：`https://scholar.google.com/citations?user=Y-ql3zMAAAAJ`（会自动提取 ID）
3) **学者姓名**：`Ian Goodfellow,DeepMind`（常见名建议带机构）

## 响应格式（统一 JSON schema）

所有 SSE 事件的 JSON 使用统一 schema（Scholar/GitHub/PK 复用）：

```json
{
  "source": "scholar",
  "event_type": "start|progress|data|final|error|end",
  "message": "人类可读文本（可选）",
  "step": "逻辑步骤名（可选）",
  "progress": 0,
  "payload": { "结构化数据（可选）" },
  "type": "legacy type（可选，兼容旧前端）",
  "content": "legacy content（可选，兼容旧前端）"
}
```

约定：
- `event_type=end` 必发（无论成功/失败/取消/超时）
- `event_type=error` 时 `payload` 统一为 `{code,message,retryable,detail}`

### 关键事件：reportData

报告链接会以 `event_type=data` 发出，同时保留旧字段以兼容旧前端：

```json
{
  "source": "scholar",
  "event_type": "data",
  "step": "report_data",
  "type": "reportData",
  "payload": {
    "jsonUrl": "…",
    "htmlUrl": "…",
    "researcherName": "…",
    "scholarId": "…"
  },
  "content": {
    "jsonUrl": "…",
    "htmlUrl": "…",
    "researcherName": "…",
    "scholarId": "…"
  }
}
```

## 前端调用示例（POST + fetch 解析 SSE）

推荐用 `fetch()` 读流（POST 需要请求头，原生 `EventSource` 不支持）。

```js
import { postSSE } from "../legacy/frontend_streaming_integration";

postSSE(`${API_BASE_URL}/api/stream`, { query: "Y-ql3zMAAAAJ" }, {
  userId: "u1",
  onEvent: (evt) => console.log(evt),
});
```

通用解析器见：`docs/legacy/frontend_streaming_integration.md`

## 最新报告接口（推荐）

需要刷新/断线恢复时，前端推荐直接拉取 DB 缓存中的最新报告：

`GET /api/scholar/report?scholar_id=<id>&max_age_days=30`

返回：
- `report`: 最新 report（DB 缓存）
- `completeness`: 完整度（哪些模块齐全/缺失）
- `last_updated`: DB 缓存更新时间
