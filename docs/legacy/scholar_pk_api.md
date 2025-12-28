# Scholar PK API 文档

本文档介绍了 Scholar PK API 的使用方法，该 API 用于比较两位学术研究者的学术成就。

## API 端点

```
POST /api/scholar-pk
```

## 请求格式

请求体应为 JSON 格式，包含以下字段：

```json
{
  "researcher1": "研究者1的姓名或Scholar ID",
  "researcher2": "研究者2的姓名或Scholar ID"
}
```

### 参数说明

- `researcher1`：第一位研究者的姓名或 Google Scholar ID
- `researcher2`：第二位研究者的姓名或 Google Scholar ID

### 输入格式

对于每个研究者，您可以使用以下格式之一：

1. **Google Scholar ID**（例如：`Y-ql3zMAAAAJ`）
   - 这是最准确的搜索方式
   - 直接从研究者的 Google Scholar 页面 URL 中提取

2. **Google Scholar URL**（例如：`https://scholar.google.com/citations?user=Y-ql3zMAAAAJ`）
   - 系统会自动提取 URL 中的 ID
   - 同样非常准确

3. **研究者姓名**（例如：`Daiheng Gao`）
   - 对于独特的名字，直接输入姓名通常足够
   - 对于常见名字，可能需要添加额外信息（例如：`Ian Goodfellow,DeepMind`）

## 响应格式（SSE）

API 返回的是一个 Server-Sent Events (SSE) 流；服务端只输出 `data: {json}\n\n`，前端按行解析 `data:` 后的 JSON 即可。

### ✅ 统一 JSON schema（推荐前端按这套解析）

```json
{
  "source": "scholar",
  "event_type": "start|progress|data|final|error|end",
  "message": "人类可读文本（可选）",
  "step": "逻辑步骤名（可选）",
  "progress": 0,
  "payload": { "任意结构化数据（可选）" },
  "type": "legacy type（可选，兼容旧前端）",
  "content": { "legacy content（可选，兼容旧前端）" }
}
```

约定：
- `event_type=end` 必发（无论成功/失败/取消/超时）
- 错误统一为 `event_type=error`，且 `payload` 统一为 `{code,message,retryable,detail}`

### 关键数据：`pkData` / `reportData`

为兼容旧前端，PK 的关键数据会以 `event_type=data` 发送，同时保留 `type/content`：

1) **pkData**（PK 结果）
```json
{
  "source": "scholar",
  "event_type": "data",
  "step": "pk_result",
  "type": "pkData",
  "payload": { /* PK 结果结构化数据 */ },
  "content": { /* 与 payload 相同（兼容旧前端） */ }
}
```

2) **reportData**（报告链接）
```json
{
  "source": "scholar",
  "event_type": "data",
  "step": "pk_report",
  "type": "reportData",
  "payload": { "jsonUrl": "..." },
  "content": { "jsonUrl": "..." }
}
```

## 示例

### 请求示例

```bash
curl -X POST http://localhost:5001/api/scholar-pk \
  -H "Content-Type: application/json" \
  -d '{"researcher1": "Y-ql3zMAAAAJ", "researcher2": "iYN86KEAAAAJ"}'
```

### 响应示例（节选）

```
data: {"source":"scholar","event_type":"start","message":"Start PK","step":"start"}

data: {"source":"scholar","event_type":"progress","message":"Fetching profiles...","step":"fetch_profile","progress":10}

data: {"source":"scholar","event_type":"data","step":"pk_result","type":"pkData","payload":{...},"content":{...}}

data: {"source":"scholar","event_type":"data","step":"pk_report","type":"reportData","payload":{...},"content":{...}}

data: {"source":"scholar","event_type":"end"}
```

## 测试页面

您可以使用 `frontend/scholar_pk_test.html` 页面来测试 API。只需在浏览器中打开该页面，输入两位研究者的信息，然后点击 "Start PK" 按钮。

## 错误处理

API 可能返回以下错误：

- 400 Bad Request：请求格式不正确或缺少必要参数
- 500 Internal Server Error：服务器内部错误

## 注意事项

1. API 使用 Google Scholar 数据，可能受到 Google 的访问限制
2. 对于非常知名的研究者，数据检索可能需要较长时间
3. 建议使用 Scholar ID 而不是姓名，以获得最准确的结果
