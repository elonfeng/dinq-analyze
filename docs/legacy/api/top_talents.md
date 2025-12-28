# Top 学者查询 API

该接口用于获取系统中的顶尖学者列表。

## 接口信息

- **URL**: `{API_BASE_URL}/api/top-talents`
- **方法**: GET
- **响应格式**: JSON

## 查询参数

| 参数名 | 类型 | 必填 | 描述 |
|-------|-----|------|------|
| count | integer | 否 | 返回的学者数量，默认为 5，范围 1-20 |

## 响应格式

### 成功响应

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

## 响应字段说明

| 字段名 | 类型 | 描述 |
|-------|-----|------|
| success | boolean | 请求是否成功 |
| count | integer | 返回的学者数量 |
| talents | array | 学者列表 |
| talents[].name | string | 学者姓名 |
| talents[].affiliation | string | 所属机构 |
| talents[].research_fields | string | 研究领域，以逗号分隔 |
| talents[].h_index | integer | H指数 |
| talents[].total_citations | integer | 总引用次数 |
| talents[].scholar_id | string | Google Scholar ID |
| talents[].photo_url | string | 头像URL |

## 使用示例

### JavaScript 示例

```javascript
// 使用 fetch API
fetch(`${API_BASE_URL}/api/top-talents?count=10`)
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      // 处理学者数据
      const talents = data.talents;
      console.log(`获取到 ${data.count} 位顶尖学者`);
      
      // 遍历学者列表
      talents.forEach(talent => {
        console.log(`姓名: ${talent.name}`);
        console.log(`机构: ${talent.affiliation}`);
        console.log(`H指数: ${talent.h_index}`);
        console.log(`总引用: ${talent.total_citations}`);
        console.log(`研究领域: ${talent.research_fields}`);
        console.log(`Scholar ID: ${talent.scholar_id}`);
        console.log(`头像: ${talent.photo_url}`);
        console.log('---');
      });
    } else {
      console.error('Error:', data.error);
    }
  })
  .catch(error => {
    console.error('Fetch error:', error);
  });
```

### React 示例

```jsx
import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from './config';

function TopTalents() {
  const [talents, setTalents] = useState([]);
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchTalents();
  }, [count]);

  const fetchTalents = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/top-talents?count=${count}`);
      const data = await response.json();
      
      if (data.success) {
        setTalents(data.talents);
      } else {
        setError(data.error || '获取数据失败');
      }
    } catch (error) {
      setError(`请求错误: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCountChange = (e) => {
    const newCount = parseInt(e.target.value);
    if (newCount >= 1 && newCount <= 20) {
      setCount(newCount);
    }
  };

  return (
    <div className="top-talents">
      <h2>顶尖学者列表</h2>
      
      <div className="controls">
        <label>
          显示数量:
          <input 
            type="number" 
            min="1" 
            max="20" 
            value={count} 
            onChange={handleCountChange} 
          />
        </label>
        <button onClick={fetchTalents} disabled={loading}>
          {loading ? '加载中...' : '刷新'}
        </button>
      </div>
      
      {error && <div className="error">{error}</div>}
      
      {loading ? (
        <div className="loading">加载中...</div>
      ) : (
        <div className="talents-list">
          {talents.map((talent, index) => (
            <div key={index} className="talent-card">
              <div className="talent-photo">
                <img src={talent.photo_url} alt={talent.name} />
              </div>
              <div className="talent-info">
                <h3>{talent.name}</h3>
                <p className="affiliation">{talent.affiliation}</p>
                <p className="fields">{talent.research_fields}</p>
                <div className="stats">
                  <div className="stat">
                    <span className="label">H指数</span>
                    <span className="value">{talent.h_index}</span>
                  </div>
                  <div className="stat">
                    <span className="label">总引用</span>
                    <span className="value">{talent.total_citations}</span>
                  </div>
                </div>
                <a 
                  href={`https://scholar.google.com/citations?user=${talent.scholar_id}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="scholar-link"
                >
                  查看 Google Scholar
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default TopTalents;
```

## 错误处理

- 如果 `count` 参数超出范围（1-20），API 将返回 400 Bad Request
- 如果服务器内部错误，API 将返回 500 Internal Server Error

## 性能考虑

- 该 API 返回的数据量相对较小，适合频繁调用
- 考虑在客户端缓存结果，减少重复请求
- 可以实现分页加载，先加载少量数据，然后根据用户需求加载更多
