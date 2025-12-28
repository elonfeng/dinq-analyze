# 等待列表 API 接口文档

本文档描述了等待列表相关的 API 接口规范，包括请求方法、URL、参数和响应格式。

## 基本信息

- **基础URL**: 与主应用相同
- **认证方式**: 通过请求头中的 `Userid` 或 `userid` 字段提供用户ID，或通过 `Authorization: Bearer {token}` 提供 Firebase 令牌
- **响应格式**: 所有API响应均为JSON格式

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

### 1. 加入等待列表

将当前用户添加到等待列表，或更新现有的等待列表条目。

**请求**:

```
POST /api/waiting-list/join
```

**请求体**:

```json
{
  "email": "user@example.com",
  "name": "用户全名",
  "organization": "用户组织或公司",
  "job_title": "用户职位",
  "reason": "加入等待列表的原因",
  "additional_field1": "额外字段1",
  "additional_field2": "额外字段2"
}
```

**请求字段说明**:

| 字段名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| email | String | 是 | 用户电子邮件地址 |
| name | String | 是 | 用户全名 |
| organization | String | 否 | 用户组织或公司 |
| job_title | String | 否 | 用户职位 |
| reason | String | 否 | 加入等待列表的原因 |
| [additional_fields] | Any | 否 | 任何额外字段都将存储在元数据中 |

**响应**:

```json
{
  "success": true,
  "message": "Successfully added to waiting list",
  "entry": {
    "id": 1,
    "user_id": "firebase_user_id",
    "email": "user@example.com",
    "name": "用户全名",
    "organization": "用户组织或公司",
    "job_title": "用户职位",
    "reason": "加入等待列表的原因",
    "status": "pending",
    "extra_data": {
      "additional_field1": "额外字段1",
      "additional_field2": "额外字段2"
    },
    "created_at": "2023-04-15T08:49:27",
    "updated_at": "2023-04-15T08:49:27"
  }
}
```

### 2. 获取等待列表状态

获取当前用户的等待列表状态。

**请求**:

```
GET /api/waiting-list/status
```

**响应** (如果找到条目):

```json
{
  "success": true,
  "entry": {
    "id": 1,
    "user_id": "firebase_user_id",
    "email": "user@example.com",
    "name": "用户全名",
    "organization": "用户组织或公司",
    "job_title": "用户职位",
    "reason": "加入等待列表的原因",
    "status": "pending",
    "extra_data": {
      "additional_field1": "额外字段1",
      "additional_field2": "额外字段2"
    },
    "created_at": "2023-04-15T08:49:27",
    "updated_at": "2023-04-15T08:49:27",
    "approved_at": null,
    "approved_by": null
  }
}
```

**响应** (如果未找到条目):

```json
{
  "success": false,
  "error": "Waiting list entry not found"
}
```

### 3. 获取等待列表条目

获取等待列表条目，支持按状态筛选。此接口需要经过验证的用户权限。

**请求**:

```
GET /api/waiting-list/entries?status=pending&limit=10&offset=0
```

**查询参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| status | String | 否 | 按状态筛选 (pending, approved, rejected) |
| limit | Integer | 否 | 返回的最大条目数，默认为100，最大为100 |
| offset | Integer | 否 | 分页偏移量，默认为0 |

**响应**:

```json
{
  "success": true,
  "total": 42,
  "limit": 10,
  "offset": 0,
  "entries": [
    {
      "id": 1,
      "user_id": "firebase_user_id_1",
      "email": "user1@example.com",
      "name": "用户1",
      "organization": "组织1",
      "job_title": "职位1",
      "reason": "原因1",
      "status": "pending",
      "extra_data": { ... },
      "created_at": "2023-04-15T08:49:27",
      "updated_at": "2023-04-15T08:49:27",
      "approved_at": null,
      "approved_by": null
    },
    {
      "id": 2,
      "user_id": "firebase_user_id_2",
      "email": "user2@example.com",
      "name": "用户2",
      "organization": "组织2",
      "job_title": "职位2",
      "reason": "原因2",
      "status": "pending",
      "extra_data": { ... },
      "created_at": "2023-04-14T10:30:00",
      "updated_at": "2023-04-14T10:30:00",
      "approved_at": null,
      "approved_by": null
    }
    // 更多条目...
  ]
}
```

### 4. 更新等待列表条目状态

更新等待列表条目的状态。此接口需要经过验证的用户权限。

**请求**:

```
POST /api/waiting-list/update-status
```

**请求体**:

```json
{
  "user_id": "firebase_user_id",
  "status": "approved"
}
```

**请求字段说明**:

| 字段名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| user_id | String | 是 | 要更新的条目的用户ID |
| status | String | 是 | 新状态 (pending, approved, rejected) |

**响应**:

```json
{
  "success": true,
  "message": "Successfully updated status to 'approved'",
  "entry": {
    "id": 1,
    "user_id": "firebase_user_id",
    "email": "user@example.com",
    "name": "用户全名",
    "status": "approved",
    "updated_at": "2023-04-16T09:30:00",
    "approved_at": "2023-04-16T09:30:00",
    "approved_by": "admin_user_id"
  }
}
```

## 字段说明

### 等待列表条目字段

| 字段名 | 类型 | 描述 |
|-------|------|------|
| id | Integer | 条目ID |
| user_id | String | 用户ID（来自认证系统） |
| email | String | 用户电子邮件地址 |
| name | String | 用户全名 |
| organization | String | 用户组织或公司 |
| job_title | String | 用户职位 |
| reason | String | 加入等待列表的原因 |
| status | String | 状态（pending, approved, rejected） |
| extra_data | Object | 额外元数据（JSON格式） |
| created_at | String | 创建时间（ISO格式） |
| updated_at | String | 更新时间（ISO格式） |
| approved_at | String | 批准时间（ISO格式） |
| approved_by | String | 批准人的用户ID |

## 错误码

| 状态码 | 描述 |
|-------|------|
| 400 | 请求参数错误 |
| 401 | 未认证或认证失败 |
| 403 | 无权访问 |
| 500 | 服务器内部错误 |

## 使用示例

### 加入等待列表

```bash
curl -X POST -H "Userid: firebase_user_id" -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "name": "用户全名",
    "organization": "用户组织或公司",
    "job_title": "用户职位",
    "reason": "加入等待列表的原因",
    "additional_field1": "额外字段1"
  }' \
  http://localhost:5001/api/waiting-list/join
```

### 获取等待列表状态

```bash
curl -H "Userid: firebase_user_id" http://localhost:5001/api/waiting-list/status
```

### 获取等待列表条目

```bash
curl -H "Userid: firebase_user_id" http://localhost:5001/api/waiting-list/entries?status=pending
```

### 更新等待列表条目状态

```bash
curl -X POST -H "Userid: admin_user_id" -H "Content-Type: application/json" \
  -d '{
    "user_id": "firebase_user_id",
    "status": "approved"
  }' \
  http://localhost:5001/api/waiting-list/update-status
```

