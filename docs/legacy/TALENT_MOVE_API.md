# 人才流动API接口文档

## 概述

人才流动API提供完整的人才流动信息管理功能，包括查询、搜索、统计和新增等操作。所有接口都支持分页查询，并提供了完善的错误处理机制。

**基础URL**: `/api/talent-move`  
**内容类型**: `application/json`  
**认证**: 无需认证

---

## 接口列表

### 1. 分页查询人才流动信息

**接口**: `GET /api/talent-move/list`

**描述**: 分页查询人才流动信息，支持多种筛选条件

**请求参数**:

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| page | Integer | 否 | 1 | 页码，从1开始 |
| page_size | Integer | 否 | 20 | 每页大小，最大100 |


**请求示例**:
```bash
curl "/api/talent-move/list?page=1&page_size=10&person_name=John"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "moves": [
      {
        "id": 1,
        "person_name": "John Smith",
        "from_company": "Google",
        "to_company": "OpenAI",
        "salary": "$500K",
        "avatar_url": "https://example.com/avatar.jpg",
        "post_image_url": "https://example.com/image.jpg",
        "tweet_url": "https://twitter.com/status/123",
        "query": "tbpn",
        "created_at": "2025-01-10T10:30:00",
        "talent_description": "John Smith moved from Google to OpenAI...",
        "age": 35,
        "work_experience": "[{\"from\": \"2021\", \"to\": \"2024\", \"company\": \"Google\", \"position\": \"Senior Engineer\"}]",
        "education": "[{\"school\": \"Stanford\", \"major\": \"Computer Science\", \"time\": \"2015-2019\"}]",
        "major_achievement": "[{\"title\": \"AI Breakthrough\", \"description\": \"Led major AI project\"}]"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_count": 97,
      "total_pages": 10
    }
  }
}
```

---

### 2. 根据ID获取人才流动信息

**接口**: `GET /api/talent-move/{move_id}`

**描述**: 根据记录ID获取单条人才流动信息

**路径参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| move_id | Integer | 是 | 记录ID |

**请求示例**:
```bash
curl "/api/talent-move/1"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "person_name": "John Smith",
    "from_company": "Google",
    "to_company": "OpenAI",
    "salary": "$500K",
    "avatar_url": "https://example.com/avatar.jpg",
    "post_image_url": "https://example.com/image.jpg",
    "tweet_url": "https://twitter.com/status/123",
    "query": "tbpn",
    "created_at": "2025-01-10T10:30:00",
    "talent_description": "John Smith moved from Google to OpenAI...",
    "age": 35,
    "work_experience": "[{\"from\": \"2021\", \"to\": \"2024\", \"company\": \"Google\", \"position\": \"Senior Engineer\"}]",
    "education": "[{\"school\": \"Stanford\", \"major\": \"Computer Science\", \"time\": \"2015-2019\"}]",
    "major_achievement": "[{\"title\": \"AI Breakthrough\", \"description\": \"Led major AI project\"}]"
  }
}
```

**错误响应** (记录不存在):
```json
{
  "success": false,
  "error": "记录不存在"
}
```


### 3. 新增人才流动信息

**接口**: `POST /api/talent-move/add`

**描述**: 新增人才流动信息，AI会自动补充详细信息（年龄、工作经历、教育背景、主要成就）

**请求头**:
```
Content-Type: application/json
```

**请求体**:

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| person_name | String | 是 | 人员姓名 |
| from_company | String | 是 | 来源公司 |
| to_company | String | 是 | 目标公司 |
| salary | String | 否 | 薪资信息 |

**请求示例**:
```bash
curl -X POST "/api/talent-move/add" \
  -H "Content-Type: application/json" \
  -d '{
    "person_name": "Jane Doe",
    "from_company": "Microsoft",
    "to_company": "OpenAI",
    "salary": "$600K"
  }'
```

**响应示例**:
```json
{
  "success": true,
  "message": "人才流动信息添加成功",
  "data": {
    "person_name": "Jane Doe",
    "from_company": "Microsoft",
    "to_company": "OpenAI",
    "enhanced_info": {
      "age": 32,
      "work_experience": "[{\"from\": \"2020\", \"to\": \"2024\", \"company\": \"Microsoft\", \"position\": \"Senior Research Scientist\"}]",
      "education": "[{\"school\": \"MIT\", \"major\": \"Computer Science\", \"time\": \"2015-2019\"}]",
      "major_achievement": "[{\"title\": \"AI Research\", \"description\": \"Published 20+ papers on machine learning\"}]"
    }
  }
}
```

**错误响应** (字段为空):
```json
{
  "success": false,
  "error": "字段 person_name 不能为空"
}
```

**错误响应** (请求数据为空):
```json
{
  "success": false,
  "error": "请求数据不能为空"
}
```

---

## 数据字段说明

### 基础字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 记录唯一标识 |
| person_name | String | 人员姓名 |
| from_company | String | 来源公司 |
| to_company | String | 目标公司 |
| salary | String | 薪资信息 |
| avatar_url | String | 头像URL |
| post_image_url | String | 推文图片URL |
| tweet_url | String | 推文URL |
| query | String | 查询关键词 |
| created_at | String | 创建时间（ISO格式） |
| talent_description | String | 人才描述 |

### AI补充字段

| 字段名 | 类型 | 说明 | 格式 |
|--------|------|------|------|
| age | Integer | 人员年龄 | 整数 |
| work_experience | String | 工作经历 | JSON字符串 |
| education | String | 教育背景 | JSON字符串 |
| major_achievement | String | 主要成就 | JSON字符串 |

### JSON字段格式

**work_experience** (工作经历):
```json
[
  {
    "from": "2021",
    "to": "2024",
    "company": "Google",
    "position": "Senior Engineer"
  }
]
```

**education** (教育背景):
```json
[
  {
    "school": "Stanford University",
    "major": "Computer Science",
    "time": "2015-2019"
  }
]
```

**major_achievement** (主要成就):
```json
[
  {
    "title": "AI Breakthrough",
    "description": "Led major AI project"
  }
]
```

---

## 错误处理

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 错误响应格式

所有错误响应都遵循以下格式：
```json
{
  "success": false,
  "error": "错误描述信息"
}
```

### 常见错误

1. **参数验证错误** (400)
   - 必需字段为空
   - 参数类型错误
   - 参数值超出范围

2. **资源不存在** (404)
   - 记录ID不存在
   - 人员姓名未找到

3. **服务器错误** (500)
   - 数据库连接失败
   - AI服务调用失败
   - 系统内部错误

