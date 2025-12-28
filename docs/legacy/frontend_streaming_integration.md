# 前端对接指南：DINQ 统一 SSE 流式协议（POST）

说明：本文件为历史流式协议说明。新统一入口与 card 级别事件请参考 `docs/frontend/README.md`。

DINQ 的流式接口使用 Server-Sent Events (SSE) 输出，但端点是 **POST**（例如 `/api/github/analyze-stream`、`/api/stream`、`/api/scholar-pk`），因此前端通常需要用 `fetch()` + 流式读取来解析 SSE（原生 `EventSource` 仅支持 GET）。

## 1) SSE 格式（仅 data 行）

后端只输出一种格式：

```
data: {json}\n\n
```

`{json}` 采用统一 schema：

```json
{
  "source": "github|scholar|linkedin|...",
  "event_type": "start|progress|data|final|error|end",
  "message": "可选：人类可读文本",
  "step": "可选：逻辑步骤名",
  "progress": 0,
  "payload": { "可选：结构化数据" },
  "type": "可选：legacy type（兼容旧前端）",
  "content": "可选：legacy content（兼容旧前端）"
}
```

约定：
- `event_type=end` 必发（无论成功/失败/取消/超时）
- `event_type=error` 时，`payload` 统一为 `{code,message,retryable,detail}`

## 2) 必要请求头

大多数流式端点需要：
- `Accept: text/event-stream`
- `Content-Type: application/json`
- `Userid: <你的用户 ID>`（后端用来做鉴权/用量/缓存隔离）

## 3) JS 参考实现（fetch + ReadableStream）

下面是一个最小可用的 SSE 解析器：按 `\n\n` 分帧、只处理 `data:` 行、对 `data:` 后面的 JSON 做 `JSON.parse`。

```js
export async function postSSE(url, body, { userId, onEvent, signal } = {}) {
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
      "Userid": userId ?? "anonymous",
    },
    body: JSON.stringify(body),
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

    // SSE frame boundary: blank line
    while (true) {
      const idx = buffer.indexOf("\n\n");
      if (idx === -1) break;

      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      for (const line of frame.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;

        const jsonText = trimmed.slice("data:".length).trim();
        if (!jsonText) continue;

        let evt;
        try { evt = JSON.parse(jsonText); } catch { continue; }
        onEvent?.(evt);

        if (evt?.event_type === "end") return;
      }
    }
  }
}
```

## 4) 取消/中断语义

前端取消：建议使用 `AbortController` 中断 `fetch()`；后端会检测客户端断开并触发 `cancel_event`，尽快停止抓取/分析并进入统一收尾（最终仍会尽力发送 `end`，但在网络断开时可能无法送达）。

```js
const ac = new AbortController();
postSSE("/api/scholar-pk", { researcher1: "...", researcher2: "..." }, {
  userId: "u1",
  signal: ac.signal,
  onEvent: (evt) => console.log(evt),
});
// 取消
ac.abort();
```

## 5) 后台 enrich job（job_id → SSE）

（已移除）旧版 `async_enrich/enrichJobId` 后台补齐机制已删除；`/api/stream` 不会再返回 `enrichJobId`，也不会触发后台补齐 job。

## 6) 获取最新报告（推荐）

需要刷新/断线恢复时，前端可直接拉取 DB 缓存中的最新报告：

- `GET /api/scholar/report?scholar_id=<id>&max_age_days=30`

## 7) 推荐数据流（最稳、最省事）

1. 调用 `/api/stream` → 收到 `reportData`（`jsonUrl/htmlUrl/...`）
2. 需要刷新时，可调用 `GET /api/scholar/report?...` 拉取 DB 缓存中的最新报告

## 8) 三个常用接口示例（前端）

下面示例统一用上面的 `postSSE()`（fetch 读流解析 SSE）。

### A) Scholar 单人分析：`POST /api/stream`

```js
postSSE(`${API_BASE_URL}/api/stream`, {
  query: "Y-ql3zMAAAAJ",
}, {
  userId: "u1",
  onEvent: (evt) => {
    // 关键：reportData 会携带 jsonUrl/htmlUrl/...
    if (evt.type === "reportData") console.log("reportData:", evt.content ?? evt.payload);
    if (evt.event_type === "error") console.error("error:", evt.payload);
  },
});
```

### B) Scholar PK：`POST /api/scholar-pk`

```js
postSSE(`${API_BASE_URL}/api/scholar-pk`, {
  researcher1: "Y-ql3zMAAAAJ",
  researcher2: "ZUeyIxMAAAAJ",
}, {
  userId: "u1",
  onEvent: (evt) => {
    // 关键：pkData/reportData 以 event_type=data 发出，同时保留 legacy type/content
    if (evt.type === "pkData") console.log("pk result:", evt.content ?? evt.payload);
    if (evt.type === "reportData") console.log("pk report:", evt.content ?? evt.payload);
  },
});
```

### C) GitHub 分析：`POST /api/github/analyze-stream`

```js
postSSE(`${API_BASE_URL}/api/github/analyze-stream`, {
  username: "octocat",
}, {
  userId: "u1",
  onEvent: (evt) => {
    // 按统一 schema 处理：start/progress/final/error/end
    if (evt.event_type === "final") console.log("final:", evt.payload);
    if (evt.event_type === "error") console.error("error:", evt.payload);
  },
});
```
