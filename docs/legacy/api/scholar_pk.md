# 学者 PK API

该接口用于比较两位学者的学术成就，生成对比数据和评论。

## 接口信息

- **URL**: `{API_BASE_URL}/api/scholar-pk`
- **方法**: POST
- **请求格式**: JSON
- **响应格式**: Server-Sent Events (SSE)

## 请求体

```json
{
  "researcher1": "学者1的姓名或Scholar ID",
  "researcher2": "学者2的姓名或Scholar ID"
}
```

## 参数说明

- `researcher1`: 第一位学者的姓名或 Google Scholar ID
- `researcher2`: 第二位学者的姓名或 Google Scholar ID

### 输入格式说明

`researcher1` 和 `researcher2` 参数支持以下几种格式:

1. **Google Scholar ID**（例如：`Y-ql3zMAAAAJ`）
2. **Google Scholar URL**（例如：`https://scholar.google.com/citations?user=Y-ql3zMAAAAJ`）
3. **学者姓名**（例如：`Daiheng Gao`）
   - 对于常见姓名，建议添加机构信息（例如：`Ian Goodfellow,DeepMind`）

## 响应消息类型

该接口返回的是一个 Server-Sent Events (SSE) 流，包含以下类型的消息：

### 1. thinkTitle

思考过程的标题。

```json
{
  "type": "thinkTitle",
  "content": "标题内容"
}
```

### 2. thinkContent

思考过程的内容。

```json
{
  "type": "thinkContent",
  "content": "内容",
  "state": "thinking|completed"
}
```

### 3. pkState

PK 过程的状态。

```json
{
  "type": "pkState",
  "content": "状态内容",
  "state": "thinking|completed|error"
}
```

### 4. pkData

PK 结果数据，包含两位学者的对比信息。

```json
{
  "type": "pkData",
  "content": {
    "researcher1": {
      "name": "学者1姓名",
      "affiliation": "机构",
      "research_fields": ["领域1", "领域2"],
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
      "name": "学者2姓名",
      "affiliation": "机构",
      "research_fields": ["领域1", "领域2"],
      "scholar_id": "Scholar ID",
      "total_citations": 5000,
      "h_index": 30,
      "top_tier_papers": 25,
      "first_author_papers": 15,
      "first_author_citations": 2000,
      "most_cited_paper": {
        "title": "论文标题",
        "venue": "发表场所",
        "year": 2018,
        "citations": 1000
      }
    },
    "roast": "幽默的对比评论"
  }
}
```

### 5. reportData

PK报告数据URL，用于获取完整的PK数据。

```json
{
  "type": "reportData",
  "content": {
    "jsonUrl": "http://example.com/reports/pk_Researcher1_ID_vs_Researcher2_ID.json",
    "researcher1Name": "学者1姓名",
    "researcher2Name": "学者2姓名",
    "scholarId1": "学者1 ID",
    "scholarId2": "学者2 ID"
  }
}
```

### 6. finalContent

最终结果，通常是 Markdown 格式的总结文本。

```json
{
  "type": "finalContent",
  "content": "最终结果的Markdown格式文本"
}
```

## 使用示例

### JavaScript 示例

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
    if (data.type === "thinkTitle") {
      console.log("思考标题:", data.content);
      // 更新UI显示思考标题...
    } else if (data.type === "thinkContent" || data.type === "pkState") {
      console.log("思考内容/状态:", data.content);
      // 更新UI显示思考内容或状态...
    } else if (data.type === "pkData") {
      // 处理 PK 数据
      const pkResult = data.content;
      console.log("PK结果:", pkResult);

      // 提取关键信息
      const researcher1 = pkResult.researcher1;
      const researcher2 = pkResult.researcher2;
      const roast = pkResult.roast;

      // 更新UI显示PK结果...
    } else if (data.type === "reportData") {
      // 处理报告数据 URL
      const reportData = data.content;
      console.log("完整PK数据URL:", reportData.jsonUrl);

      // 可以创建一个链接或按钮指向这个URL
      // 例如：创建一个链接元素
      const linkElement = document.createElement('a');
      linkElement.href = reportData.jsonUrl;
      linkElement.textContent = '查看完整PK数据';
      linkElement.target = '_blank';
      // 将链接添加到页面上
      // document.getElementById('report-links').appendChild(linkElement);
    } else if (data.type === "finalContent") {
      console.log("最终结果:", data.content);
      // 更新UI显示最终结果...
      eventSource.close();
    }
  };

  eventSource.onerror = function(error) {
    console.error("EventSource错误:", error);
    eventSource.close();
  };
})
.catch(error => {
  console.error('Error:', error);
});
```

### React 示例

```jsx
import React, { useState } from 'react';
import { API_BASE_URL } from './config';

function ScholarPK() {
  const [researcher1, setResearcher1] = useState('');
  const [researcher2, setResearcher2] = useState('');
  const [thinking, setThinking] = useState([]);
  const [pkData, setPkData] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [finalContent, setFinalContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const startPK = () => {
    if (!researcher1 || !researcher2) {
      setError('请输入两位学者的信息');
      return;
    }

    setLoading(true);
    setThinking([]);
    setPkData(null);
    setReportData(null);
    setFinalContent('');
    setError(null);

    const requestData = {
      researcher1,
      researcher2
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

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'thinkTitle':
            setThinking(prev => [...prev, { type: 'title', content: data.content }]);
            break;
          case 'thinkContent':
          case 'pkState':
            setThinking(prev => [...prev, {
              type: 'content',
              content: data.content,
              state: data.state
            }]);
            break;
          case 'pkData':
            setPkData(data.content);
            break;
          case 'reportData':
            setReportData(data.content);
            break;
          case 'finalContent':
            setFinalContent(data.content);
            setLoading(false);
            eventSource.close();
            break;
          default:
            break;
        }
      };

      eventSource.onerror = () => {
        setError('连接错误，请重试');
        setLoading(false);
        eventSource.close();
      };
    })
    .catch(error => {
      setError(`请求错误: ${error.message}`);
      setLoading(false);
    });
  };

  return (
    <div className="scholar-pk">
      <div className="input-section">
        <div className="form-group">
          <label>学者 1:</label>
          <input
            type="text"
            value={researcher1}
            onChange={(e) => setResearcher1(e.target.value)}
            placeholder="姓名或Scholar ID"
          />
        </div>

        <div className="form-group">
          <label>学者 2:</label>
          <input
            type="text"
            value={researcher2}
            onChange={(e) => setResearcher2(e.target.value)}
            placeholder="姓名或Scholar ID"
          />
        </div>

        <button onClick={startPK} disabled={loading}>
          {loading ? '对比中...' : '开始PK'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="thinking-process">
        {thinking.map((item, index) => (
          <div key={index} className={`thinking-item ${item.type} ${item.state || ''}`}>
            {item.content}
          </div>
        ))}
      </div>

      {pkData && (
        <div className="pk-result">
          <div className="roast">{pkData.roast}</div>

          <div className="comparison">
            <div className="researcher">
              <h3>{pkData.researcher1.name}</h3>
              <p>所属机构: {pkData.researcher1.affiliation}</p>
              <p>总引用: {pkData.researcher1.total_citations}</p>
              <p>H指数: {pkData.researcher1.h_index}</p>
              {/* 显示更多数据... */}
            </div>

            <div className="researcher">
              <h3>{pkData.researcher2.name}</h3>
              <p>所属机构: {pkData.researcher2.affiliation}</p>
              <p>总引用: {pkData.researcher2.total_citations}</p>
              <p>H指数: {pkData.researcher2.h_index}</p>
              {/* 显示更多数据... */}
            </div>
          </div>

          {reportData && (
            <div className="data-urls">
              <h3>数据链接</h3>
              <p>
                <a href={reportData.jsonUrl} target="_blank" rel="noopener noreferrer">
                  查看完整PK数据
                </a>
              </p>
            </div>
          )}
        </div>
      )}

      {finalContent && (
        <div className="final-content">
          {/* 使用Markdown渲染器显示finalContent */}
        </div>
      )}
    </div>
  );
}

export default ScholarPK;
```

## 错误处理

- 如果请求体格式不正确，API 将返回 400 Bad Request
- 如果无法找到学者，API 将在 finalContent 中返回错误信息
- 如果连接中断，客户端应该实现重试逻辑

## 性能考虑

- 该 API 可能需要较长时间才能返回完整结果，特别是对于知名学者
- 建议实现超时处理和用户反馈机制
- 考虑在客户端缓存结果，减少重复请求
