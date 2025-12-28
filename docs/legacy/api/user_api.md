# 用户 API 接口文档

本文档描述了用户相关的 API 接口规范，包括请求方法、URL、参数和响应格式。

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

### 1. 获取当前用户信息

获取当前认证用户的信息。如果用户在数据库中不存在，将自动创建用户记录。

**请求**:

```
GET /api/user/me
```

**响应**:

```json
{
  "success": true,
  "user": {
    "user_id": "firebase_user_id",
    "display_name": "用户名称",
    "email": "user@example.com",
    "profile_picture": "https://example.com/photo.jpg",
    "is_activated": true,
    "activation_code": "ABC123",
    "activated_at": "2023-04-15T08:49:27",
    "user_type": "standard",
    "preferences": null,
    "last_login": "2023-04-15T08:49:27",
    "created_at": "2023-04-01T10:30:00",
    "updated_at": "2023-04-15T08:49:27",
    "has_used_activation_code": true,
    "activation_code_details": {
      "code": "ABC123",
      "used_at": "2023-04-15T08:49:27",
      "created_by": "admin",
      "created_at": "2023-04-01T10:30:00",
      "expires_at": null,
      "batch_id": "batch_001",
      "notes": "测试激活码"
    }
  }
}
```

**字段说明**:

| 字段名 | 类型 | 描述 |
|-------|------|------|
| user_id | String | 用户唯一标识符（来自认证系统） |
| display_name | String | 用户显示名称 |
| email | String | 用户电子邮件地址 |
| profile_picture | String | 用户头像URL |
| is_activated | Boolean | 用户是否已使用激活码 |
| activation_code | String | 用户使用的激活码 |
| activated_at | String | 用户激活时间（ISO格式） |
| user_type | String | 用户类型（standard, premium, admin等） |
| preferences | Object | 用户偏好设置（JSON格式） |
| last_login | String | 最后登录时间（ISO格式） |
| created_at | String | 用户创建时间（ISO格式） |
| updated_at | String | 用户信息更新时间（ISO格式） |
| has_used_activation_code | Boolean | 用户是否使用过激活码 |
| activation_code_details | Object | 激活码详细信息 |

**激活码详细信息字段**:

| 字段名 | 类型 | 描述 |
|-------|------|------|
| code | String | 激活码 |
| used_at | String | 激活码使用时间（ISO格式） |
| created_by | String | 创建激活码的用户ID |
| created_at | String | 激活码创建时间（ISO格式） |
| expires_at | String | 激活码过期时间（ISO格式），null表示永不过期 |
| batch_id | String | 批次ID |
| notes | String | 备注 |

### 2. 获取 Firebase 用户信息

获取当前用户的 Firebase 认证信息和数据库用户信息。

**请求**:

```
GET /api/user/firebase-info
```

**响应**:

```json
{
  "success": true,
  "firebase_user": {
    "uid": "firebase_user_id",
    "email": "user@example.com",
    "email_verified": true,
    "display_name": "用户名称",
    "photo_url": "https://example.com/photo.jpg",
    "phone_number": "+1234567890",
    "disabled": false,
    "creation_timestamp": 1609459200000,
    "last_sign_in_timestamp": 1640995200000,
    "providers": [
      {
        "provider_id": "google.com",
        "display_name": "用户名称",
        "email": "user@example.com",
        "photo_url": "https://example.com/photo.jpg"
      }
    ],
    "custom_claims": {
      "role": "user"
    }
  },
  "database_user": {
    // 与"获取当前用户信息"接口返回的user字段相同
  }
}
```

**Firebase 用户字段说明**:

| 字段名 | 类型 | 描述 |
|-------|------|------|
| uid | String | Firebase 用户唯一标识符 |
| email | String | 用户电子邮件地址 |
| email_verified | Boolean | 电子邮件是否已验证 |
| display_name | String | 用户显示名称 |
| photo_url | String | 用户头像URL |
| phone_number | String | 用户电话号码 |
| disabled | Boolean | 账户是否已禁用 |
| creation_timestamp | Number | 账户创建时间戳（毫秒） |
| last_sign_in_timestamp | Number | 最后登录时间戳（毫秒） |
| providers | Array | 身份提供商信息 |
| custom_claims | Object | 自定义声明 |

**身份提供商字段说明**:

| 字段名 | 类型 | 描述 |
|-------|------|------|
| provider_id | String | 提供商ID（如google.com, facebook.com等） |
| display_name | String | 提供商处的用户显示名称 |
| email | String | 提供商处的用户电子邮件 |
| photo_url | String | 提供商处的用户头像URL |

### 3. 更新当前用户信息

更新当前认证用户的信息。

**请求**:

```
PUT /api/user/me
```

**请求体**:

```json
{
  "display_name": "新用户名称",
  "email": "new.email@example.com",
  "profile_picture": "https://example.com/new-photo.jpg",
  "preferences": {
    "theme": "dark",
    "language": "zh-CN"
  }
}
```

**请求字段说明**:

| 字段名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| display_name | String | 否 | 用户显示名称 |
| email | String | 否 | 用户电子邮件地址 |
| profile_picture | String | 否 | 用户头像URL |
| preferences | Object | 否 | 用户偏好设置（JSON格式） |

**响应**:

```json
{
  "success": true,
  "user": {
    // 与"获取当前用户信息"接口返回的user字段相同，但包含更新后的值
  }
}
```

### 4. 使用激活码

使用激活码激活当前用户。

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

**请求字段说明**:

| 字段名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| code | String | 是 | 要使用的激活码 |

**响应**:

```json
{
  "success": true,
  "message": "Activation code used successfully",
  "code": "ABC123",
  "used_at": "2023-04-15T08:49:27",
  "user": {
    // 与"获取当前用户信息"接口返回的user字段相同，但包含更新后的激活状态
  }
}
```

**响应字段说明**:

| 字段名 | 类型 | 描述 |
|-------|------|------|
| message | String | 成功消息 |
| code | String | 使用的激活码 |
| used_at | String | 激活码使用时间（ISO格式） |
| user | Object | 更新后的用户信息 |

## 错误码

| 状态码 | 描述 |
|-------|------|
| 400 | 请求参数错误 |
| 401 | 未认证或认证失败 |
| 403 | 无权访问 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用（如Firebase认证服务不可用） |

## 使用示例

### 获取当前用户信息

```bash
curl -H "Userid: firebase_user_id" http://localhost:5001/api/user/me
```

### 获取 Firebase 用户信息

```bash
curl -H "Userid: firebase_user_id" http://localhost:5001/api/user/firebase-info
```

### 更新当前用户信息

```bash
curl -X PUT -H "Userid: firebase_user_id" -H "Content-Type: application/json" \
  -d '{"display_name": "新用户名称"}' \
  http://localhost:5001/api/user/me
```

### 使用激活码

```bash
curl -X POST -H "Userid: firebase_user_id" -H "Content-Type: application/json" \
  -d '{"code": "ABC123"}' \
  http://localhost:5001/api/activation-codes/use
```
