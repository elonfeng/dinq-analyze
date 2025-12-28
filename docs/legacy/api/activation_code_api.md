# 激活码 API 接口文档

本文档描述了激活码 API 的接口规范，包括请求方法、URL、参数和响应格式。

## 基本信息

- **基础URL**: 与主应用相同
- **认证方式**: 通过请求头中的 `Userid` 或 `userid` 字段提供用户ID，或通过 `Authorization: Bearer {token}` 提供 Firebase 令牌
- **权限**: 
  - 创建激活码和查询激活码列表需要经过验证的用户
  - 验证和使用激活码只需要基本认证
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

### 1. 创建激活码

创建一个新的激活码。每个用户每天最多可以创建10个激活码。

**请求**:

```
POST /api/activation-codes/create
```

**请求体**:

```json
{
  "expires_in_days": 30,  // 可选，激活码过期天数
  "batch_id": "batch-001",  // 可选，批次ID
  "notes": "For new users"  // 可选，备注
}
```

**响应**:

```json
{
  "success": true,
  "code": "ABC123",
  "created_at": "2023-04-15T08:49:27",
  "expires_at": "2023-05-15T08:49:27"  // 如果设置了过期时间
}
```

### 2. 使用激活码

使用一个激活码。每个激活码只能被使用一次。

**请求**:

```
POST /api/activation-codes/use
```

**请求体**:

```json
{
  "code": "ABC123"
}
```

**响应**:

```json
{
  "success": true,
  "message": "Activation code used successfully",
  "code": "ABC123",
  "used_at": "2023-04-15T08:49:27"
}
```

### 3. 验证激活码

验证一个激活码是否有效（存在且未被使用）。

**请求**:

```
GET /api/activation-codes/verify?code=ABC123
```

或

```
POST /api/activation-codes/verify
```

**请求体** (仅POST):

```json
{
  "code": "ABC123"
}
```

**响应** (有效):

```json
{
  "success": true,
  "message": "Activation code is valid",
  "code": "ABC123",
  "created_at": "2023-04-15T08:49:27",
  "expires_at": "2023-05-15T08:49:27"  // 如果设置了过期时间
}
```

**响应** (已使用):

```json
{
  "success": false,
  "error": "This activation code has already been used",
  "used_by": "user123",
  "used_at": "2023-04-15T08:49:27"
}
```

**响应** (已过期):

```json
{
  "success": false,
  "error": "This activation code has expired",
  "expires_at": "2023-04-15T08:49:27"
}
```

### 4. 获取激活码列表

获取当前用户创建或使用的激活码列表。

**请求**:

```
GET /api/activation-codes
```

**查询参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| is_used | Boolean | 否 | 按使用状态筛选 (true/false) |
| batch_id | String | 否 | 按批次ID筛选 |
| limit | Integer | 否 | 每页记录数，默认为100，最大为100 |
| offset | Integer | 否 | 分页偏移量，默认为0 |

**响应**:

```json
{
  "success": true,
  "total": 120,
  "limit": 100,
  "offset": 0,
  "codes": [
    {
      "id": 1,
      "code": "ABC123",
      "is_used": true,
      "created_by": "user123",
      "used_by": "user456",
      "created_at": "2023-04-15T08:49:27",
      "used_at": "2023-04-16T10:30:15",
      "expires_at": "2023-05-15T08:49:27",
      "batch_id": "batch-001",
      "notes": "For new users"
    },
    // 更多激活码...
  ]
}
```

## 错误码

| 状态码 | 描述 |
|-------|------|
| 400 | 请求参数错误或激活码无效 |
| 401 | 未认证或认证失败 |
| 403 | 无权访问 |
| 500 | 服务器内部错误 |

## 使用限制

1. 每个用户每天最多可以创建10个激活码
2. 每个激活码只能被使用一次
3. 激活码可以设置过期时间，过期后将无法使用

## 使用示例

### 创建激活码

```
POST /api/activation-codes/create
Content-Type: application/json

{
  "expires_in_days": 30,
  "notes": "For beta testers"
}
```

### 使用激活码

```
POST /api/activation-codes/use
Content-Type: application/json

{
  "code": "ABC123"
}
```

### 验证激活码

```
GET /api/activation-codes/verify?code=ABC123
```

### 获取未使用的激活码

```
GET /api/activation-codes?is_used=false
```
