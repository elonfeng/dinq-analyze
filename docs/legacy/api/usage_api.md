# API 使用统计接口文档

本文档描述了 API 使用统计接口的规范，包括请求方法、URL、参数和响应格式。

## 基本信息

- **基础URL**: 与主应用相同
- **认证方式**: 通过请求头中的 `Userid` 或 `userid` 字段提供用户ID，或通过 `Authorization: Bearer {token}` 提供 Firebase 令牌
- **权限**: 用户只能查询自己的 API 使用情况
- **响应格式**: 所有API响应均为JSON格式
- **查询限制**: 最大查询天数为30天，默认查询最近3天

## 通用响应格式

所有API响应都遵循以下格式:

```json
{
  "success": true,
  "data": { ... }  // 成功时返回的数据
}
```

或者在发生错误时:

```json
{
  "success": false,
  "error": "错误信息"
}
```

## API 端点

### 1. 获取 API 使用统计

获取当前用户的 API 使用统计信息，包括总调用次数和每日调用次数。可以选择性地包含按端点分组的调用次数和最近的调用记录。

**请求**:

```
GET /api/usage/stats
```

**查询参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| days | Integer | 否 | 查询的天数范围，默认为3天，最大为30天 |
| include_recent | Boolean | 否 | 是否包含最近的调用记录，默认为false |
| include_endpoints | Boolean | 否 | 是否包含按端点分组的调用次数，默认为false |

**响应**:

```json
{
  "success": true,
  "data": {
    "total_calls": 120,
    "days": 3,
    "daily_usage": [
      {
        "date": "2023-04-01",
        "count": 5
      },
      {
        "date": "2023-04-02",
        "count": 10
      },
      {
        "date": "2023-04-03",
        "count": 15
      }
    ],
    "endpoints": [  // 仅当include_endpoints=true时包含
      {
        "endpoint": "/api/stream",
        "count": 50
      },
      {
        "endpoint": "/api/scholar-pk",
        "count": 70
      }
    ],
    "recent_calls": [  // 仅当include_recent=true时包含
      {
        "id": 123,
        "endpoint": "/api/stream",
        "query": "Andrew Ng",
        "query_type": "scholar_name",
        "scholar_id": "DAcGzv0AAAAJ",
        "status": "success",
        "execution_time": 2.5,
        "created_at": "2023-04-15T08:49:27"
      }
    ]
  }
}
```

### 2. 获取 API 使用详情

获取当前用户的 API 使用详细记录，支持按端点和日期范围筛选，并提供分页功能。

**请求**:

```
GET /api/usage/details
```

**查询参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| endpoint | String | 否 | 按特定端点筛选 |
| start_date | String | 否 | 开始日期，ISO格式 (YYYY-MM-DD)，默认为3天前 |
| end_date | String | 否 | 结束日期，ISO格式 (YYYY-MM-DD)，默认为当前日期 |
| page | Integer | 否 | 页码，默认为1 |
| per_page | Integer | 否 | 每页记录数，默认为10，最大为50 |

**响应**:

```json
{
  "success": true,
  "data": {
    "records": [
      {
        "id": 123,
        "endpoint": "/api/stream",
        "query": "Andrew Ng",
        "status": "success",
        "execution_time": 2.5,
        "created_at": "2023-04-15T08:49:27"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 10,
      "total_count": 120,
      "total_pages": 12
    },
    "filters": {
      "endpoint": "/api/stream",
      "start_date": "2023-04-12T00:00:00",
      "end_date": "2023-04-15T23:59:59"
    }
  }
}
```

## 错误码

| 状态码 | 描述 |
|-------|------|
| 400 | 请求参数错误 |
| 401 | 未认证或认证失败 |
| 403 | 无权访问 |
| 500 | 服务器内部错误 |

## 使用示例

### 获取最近7天的API使用统计（基本信息）

```
GET /api/usage/stats?days=7
```

### 获取最近7天的API使用统计（包含端点统计和最近调用）

```
GET /api/usage/stats?days=7&include_endpoints=true&include_recent=true
```

### 获取特定端点的API使用详情

```
GET /api/usage/details?endpoint=/api/stream&page=1&per_page=20
```

### 获取特定日期范围的API使用详情

```
GET /api/usage/details?start_date=2023-04-01&end_date=2023-04-15
```

## 性能优化说明

为了优化系统资源使用，API 使用统计接口采用了以下策略：

1. 默认只查询最近3天的数据，最大查询范围限制为30天
2. 按需加载数据：只有在明确请求时才会返回端点统计和最近调用记录
3. 详情接口返回的字段已精简，只包含必要信息
4. 分页大小默认为10条记录，最大为50条记录

这些优化措施可以显著减少数据库查询负担和响应大小，提高接口性能。
