# DINQ 学术数据 API 接口文档

说明：本文件为历史接口说明，新统一入口与最新协议请优先参考 `docs/api/openapi.yaml` 与 `docs/api/README.md`。

本文档面向前端开发人员，详细介绍了 DINQ 系统提供的学术数据 API 接口。

## 基础信息

- **基础 URL**: `{API_BASE_URL}`
  - 开发环境: `http://localhost:5001`
  - 测试环境: `https://test-api.dinq.ai`
  - 生产环境: `https://api.dinq.ai`

- **请求格式**: 除非特别说明，所有请求和响应均使用 JSON 格式
- **认证方式**: 目前接口不需要认证

## 1. 单个学者查询 API

该接口用于查询单个学者的详细学术信息，支持通过姓名或 Google Scholar ID 进行查询。

### 请求

```
GET {API_BASE_URL}/api/stream
```

### 查询参数

| 参数名 | 类型 | 必填 | 描述 |
|-------|-----|------|------|
| query | string | 是 | 学者姓名、Google Scholar ID 或 URL |

### 输入格式说明

`query` 参数支持以下几种格式:

1. **Google Scholar ID**（例如：`Y-ql3zMAAAAJ`）
2. **Google Scholar URL**（例如：`https://scholar.google.com/citations?user=Y-ql3zMAAAAJ`）
3. **学者姓名**（例如：`Daiheng Gao`）
   - 对于常见姓名，建议添加机构信息（例如：`Ian Goodfellow,DeepMind`）

### 响应

该接口返回的是一个 Server-Sent Events (SSE) 流。为兼容旧版和统一前端处理，单条消息包含：

- 统一字段：
  - `source`: `"scholar"`
  - `event_type`: `"start" | "progress" | "data" | "final" | "error" | "end"`
  - `message`: 文本提示
  - `step`: 可选的阶段名称
  - `progress`: 可选进度（0-100）
  - `payload`: 结构化数据（如完整报告）
- 兼容字段（旧版仍可用）：
  - `type`: `thinkTitle` / `thinkContent` / `reportData` / `finalContent`
  - `content`: 旧版的内容字段

典型的学者报告数据事件为：

```json
{
  "source": "scholar",
  "event_type": "data",
  "type": "reportData",
  "message": "Scholar report generated",
  "payload": {
    "researcher": {
      "name": "学者姓名",
      "affiliation": "所属机构",
      "scholar_id": "Google Scholar ID",
      "h_index": 10,
      "total_citations": 1000,
      "research_fields": ["领域1", "领域2"],
      "photo_url": "头像URL"
    },
    "publication_stats": {
      "total_papers": 50,
      "first_author_papers": 20,
      "last_author_papers": 10,
      "top_tier_papers": 15,
      "first_author_citations": 500,
      "yearly_paper_count": {"2020": 5, "2021": 7, "2022": 8}
    },
    "most_cited_paper": {
      "title": "论文标题",
      "venue": "发表场所",
      "year": 2020,
      "citations": 300,
      "authors": "作者列表",
      "url": "论文URL"
    },
    "most_frequent_collaborator": {
      "full_name": "合作者姓名",
      "affiliation": "所属机构",
      "scholar_id": "Google Scholar ID",
      "coauthored_papers": 10,
      "best_paper": {
        "title": "论文标题",
        "venue": "发表场所",
        "year": 2021,
        "citations": 150
      }
    },
    "report_urls": {
      "html_url": "HTML报告URL",
      "pdf_url": "PDF报告URL",
      "session_id": "会话ID"
    }
  },
  "content": {
       "researcher": {
         "name": "学者姓名",
         "affiliation": "所属机构",
         "scholar_id": "Google Scholar ID",
         "h_index": 10,
         "total_citations": 1000,
         "research_fields": ["领域1", "领域2"],
         "photo_url": "头像URL"
       },
       "publication_stats": {
         "total_papers": 50,
         "first_author_papers": 20,
         "last_author_papers": 10,
         "top_tier_papers": 15,
         "first_author_citations": 500,
         "yearly_paper_count": {"2020": 5, "2021": 7, "2022": 8}
       },
       "most_cited_paper": {
         "title": "论文标题",
         "venue": "发表场所",
         "year": 2020,
         "citations": 300,
         "authors": "作者列表",
         "url": "论文URL"
       },
       "most_frequent_collaborator": {
         "full_name": "合作者姓名",
         "affiliation": "所属机构",
         "scholar_id": "Google Scholar ID",
         "coauthored_papers": 10,
         "best_paper": {
           "title": "论文标题",
           "venue": "发表场所",
           "year": 2021,
           "citations": 150
         }
       },
       "report_urls": {
         "html_url": "HTML报告URL",
         "pdf_url": "PDF报告URL",
         "session_id": "会话ID"
       }
     }
}
```

最终总结事件通常为：

```json
{
  "source": "scholar",
  "event_type": "final",
  "type": "finalContent",
  "message": "最终结果的Markdown格式文本",
  "content": "最终结果的Markdown格式文本"
}
```

### 示例

#### 请求示例

```javascript
// 使用 fetch API
const query = "Daiheng Gao";
const eventSource = new EventSource(`${API_BASE_URL}/api/stream?query=${encodeURIComponent(query)}`);

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log(data);

  // 根据消息类型处理数据
  if (data.type === "reportData") {
    // 处理学者报告数据
    const report = data.content;
    // 更新UI...
  } else if (data.type === "finalContent") {
    // 处理最终结果
    eventSource.close();
  }
};

eventSource.onerror = function() {
  eventSource.close();
};
```

## 2. 学者 PK API

该接口用于比较两位学者的学术成就，生成对比数据和评论。

### 请求

```
POST {API_BASE_URL}/api/scholar-pk
```

### 请求体

```json
{
  "researcher1": "学者1的姓名或Scholar ID",
  "researcher2": "学者2的姓名或Scholar ID"
}
```

### 参数说明

- `researcher1`: 第一位学者的姓名或 Google Scholar ID
- `researcher2`: 第二位学者的姓名或 Google Scholar ID

### 响应

该接口同样返回 Server-Sent Events (SSE) 流，包含以下类型的消息：

1. **thinkTitle** 和 **thinkContent**: 与单个学者查询 API 相同

2. **pkState**: PK 过程的状态
   ```json
   {
     "type": "pkState",
     "content": "状态内容",
     "state": "thinking|completed|error"
   }
   ```

3. **pkData**: PK 结果数据
   ```json
   {
     "type": "pkData",
     "content": {
       "researcher1": {
         "name": "学者1姓名",
         "affiliation": "机构",
         "scholar_id": "Scholar ID",
         "total_citations": 1000,
         "h_index": 15,
         "top_tier_papers": 10,
         "first_author_papers": 20,
         "first_author_citations": 500,
         "most_cited_paper": {
           "title": "论文标题",
           "venue": "发表场所",
           "year": 2020,
           "citations": 300
         }
       },
       "researcher2": {
         // 与 researcher1 相同的结构
       },
       "roast": "幽默的对比评论"
     }
   }
   ```

4. **finalContent**: 最终结果，与单个学者查询 API 相同

### 示例

#### 请求示例

```javascript
// 使用 fetch API
const requestData = {
  researcher1: "Y-ql3zMAAAAJ",  // Daiheng Gao
  researcher2: "iYN86KEAAAAJ"   // Ian Goodfellow
};

fetch(`${API_BASE_URL}/api/scholar-pk`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(requestData)
})
.then(response => {
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const eventSource = new EventSource(response.url);

  eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log(data);

    // 根据消息类型处理数据
    if (data.type === "pkData") {
      // 处理 PK 数据
      const pkResult = data.content;
      // 更新UI...
    } else if (data.type === "finalContent") {
      // 处理最终结果
      eventSource.close();
    }
  };

  eventSource.onerror = function() {
    eventSource.close();
  };
})
.catch(error => {
  console.error('Error:', error);
});
```

## 3. Demo Request API

该接口用于处理产品演示请求，包括获取表单信息、提交请求和查询用户的请求历史。

详细文档请参考 [Demo Request API 文档](./demo_request_api.md)。

## 4. Top 学者查询 API

该接口用于获取系统中的顶尖学者列表。

### 请求

```
GET {API_BASE_URL}/api/top-talents
```

### 查询参数

| 参数名 | 类型 | 必填 | 描述 |
|-------|-----|------|------|
| count | integer | 否 | 返回的学者数量，默认为 5，范围 1-20 |

### 响应

```json
{
  "success": true,
  "count": 5,
  "talents": [
    {
      "name": "学者姓名",
      "affiliation": "所属机构",
      "research_fields": "研究领域",
      "h_index": 50,
      "total_citations": 10000,
      "scholar_id": "Google Scholar ID",
      "photo_url": "头像URL"
    },
    // 更多学者...
  ]
}
```

### 错误响应

```json
{
  "success": false,
  "error": "错误信息"
}
```

### 示例

#### 请求示例

```javascript
// 使用 fetch API
fetch(`${API_BASE_URL}/api/top-talents?count=10`)
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      // 处理学者数据
      const talents = data.talents;
      // 更新UI...
    } else {
      console.error('Error:', data.error);
    }
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

## 错误处理

所有 API 可能返回以下 HTTP 状态码：

- **200 OK**: 请求成功
- **400 Bad Request**: 请求参数错误
- **404 Not Found**: 资源不存在
- **500 Internal Server Error**: 服务器内部错误

对于非 200 状态码，响应体通常包含错误信息：

```json
{
  "error": "错误描述"
}
```

## 最佳实践

1. **使用 Scholar ID**: 尽可能使用 Google Scholar ID 而不是姓名进行查询，以获得最准确的结果
2. **错误处理**: 实现完善的错误处理机制，特别是对于流式 API
3. **UI 反馈**: 为长时间运行的请求提供适当的加载指示器
4. **缓存策略**: 考虑在客户端缓存结果，减少重复请求
5. **响应式设计**: 确保 UI 能够适应不同大小的数据集

## 环境配置

为了支持不同环境的 API 基础 URL，建议在前端项目中使用环境变量或配置文件：

```javascript
// config.js
const config = {
  development: {
    API_BASE_URL: 'http://localhost:5001'
  },
  test: {
    API_BASE_URL: 'https://test-api.dinq.ai'
  },
  production: {
    API_BASE_URL: 'https://api.dinq.ai'
  }
};

// 根据当前环境导出配置
export const API_BASE_URL = config[process.env.NODE_ENV || 'development'].API_BASE_URL;
```

然后在 API 调用中使用：

```javascript
import { API_BASE_URL } from './config';

fetch(`${API_BASE_URL}/api/top-talents`)
  .then(response => response.json())
  .then(data => {
    // 处理数据...
  });
```

## 注意事项

1. 学者查询和 PK API 可能需要较长时间才能返回完整结果
2. 对于流式 API，确保正确处理连接关闭和错误情况
3. 系统使用 Google Scholar 数据，可能受到 Google 的访问限制
4. 建议在非工作时间进行大量测试，以避免触发 Google 的限制

## 联系方式

如有任何问题或需要进一步的帮助，请联系：

- 技术支持: support@dinq.ai
- API 文档维护: api-docs@dinq.ai
