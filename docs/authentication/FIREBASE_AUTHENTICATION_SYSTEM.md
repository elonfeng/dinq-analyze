# Firebase 认证系统文档

## 概述

DINQ项目使用Firebase Authentication作为主要的用户认证系统，提供安全可靠的用户身份验证和授权功能。

## 系统架构

### 1. 核心组件

#### Firebase配置 (`server/config/firebase_config.py`)
- Firebase Admin SDK初始化
- 服务账户密钥管理
- 开发环境认证跳过机制
- 令牌验证功能

#### 认证工具 (`server/utils/auth.py`)
- 用户认证装饰器
- 令牌验证逻辑
- 用户ID提取
- 认证状态检查

#### 用户API (`server/api/user_api.py`)
- 用户信息查询
- Firebase用户数据获取
- 数据库用户信息同步

### 2. 认证流程

```mermaid
graph TD
    A[客户端请求] --> B[检查Authorization头]
    B --> C{Bearer Token存在?}
    C -->|是| D[验证Firebase Token]
    C -->|否| E[检查Userid头]
    D --> F{Token有效?}
    F -->|是| G[提取用户ID]
    F -->|否| E
    E --> H{用户ID存在?}
    H -->|是| I[验证Firebase用户]
    H -->|否| J[认证失败]
    I --> K{用户存在?}
    K -->|是| G
    K -->|否| J
    G --> L[设置g.user_id]
    L --> M[继续处理请求]
    J --> N[返回401错误]
```

## 配置说明

### 1. 环境变量

#### 必需的环境变量
```bash
# Firebase服务账户密钥文件路径
FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/service-account-key.json

# 或者直接设置服务账户密钥内容
FIREBASE_SERVICE_ACCOUNT_KEY='{"type": "service_account", ...}'
```

#### 可选的环境变量
```bash
# 开发环境跳过认证（默认: false）
FIREBASE_SKIP_AUTH_IN_DEV=true

# 环境类型（development/production）
ENVIRONMENT=development
```

### 2. 服务账户密钥

#### 获取服务账户密钥
1. 访问 [Firebase Console](https://console.firebase.google.com/)
2. 选择项目 → 项目设置 → 服务账户
3. 生成新的私钥
4. 下载JSON文件并保存到安全位置

#### 密钥文件格式
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com",
  "client_id": "client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxxxx%40your-project-id.iam.gserviceaccount.com"
}
```

## API认证

### 1. 认证方法

#### 方法1: Bearer Token（推荐）
```bash
curl -X GET "http://localhost:5001/api/user/me" \
  -H "Authorization: Bearer YOUR_FIREBASE_ID_TOKEN"
```

#### 方法2: 用户ID头（开发环境）
```bash
curl -X GET "http://localhost:5001/api/user/me" \
  -H "Userid: USER_ID"
```

### 2. 认证装饰器

#### `@require_auth` - 基础认证
```python
from server.utils.auth import require_auth

@app.route('/api/protected')
@require_auth
def protected_endpoint():
    user_id = g.user_id  # 获取当前用户ID
    return jsonify({"user_id": user_id})
```

#### `@require_verified_user` - 验证用户认证
```python
from server.utils.auth import require_verified_user

@app.route('/api/verified-only')
@require_verified_user
def verified_only_endpoint():
    user_id = g.user_id  # 获取已验证用户ID
    return jsonify({"user_id": user_id})
```

### 3. 认证响应

#### 成功认证
```json
{
  "success": true,
  "data": {
    "user_id": "firebase_user_id",
    "email": "user@example.com",
    "verified": true
  }
}
```

#### 认证失败
```json
{
  "success": false,
  "error": "Authentication required",
  "code": "AUTH_REQUIRED"
}
```

## 用户管理

### 1. 用户信息API

#### 获取当前用户信息
```bash
GET /api/user/me
Authorization: Bearer YOUR_TOKEN
```

**响应**:
```json
{
  "success": true,
  "user": {
    "id": "firebase_user_id",
    "email": "user@example.com",
    "display_name": "User Name",
    "created_at": "2023-01-01T00:00:00Z",
    "last_login": "2023-01-01T12:00:00Z"
  }
}
```

#### 获取Firebase用户详情
```bash
GET /api/user/firebase-info
Authorization: Bearer YOUR_TOKEN
```

**响应**:
```json
{
  "success": true,
  "firebase_user": {
    "uid": "firebase_user_id",
    "email": "user@example.com",
    "email_verified": true,
    "display_name": "User Name",
    "photo_url": "https://...",
    "providers": ["password", "google.com"],
    "custom_claims": {},
    "metadata": {
      "creation_time": "2023-01-01T00:00:00Z",
      "last_sign_in_time": "2023-01-01T12:00:00Z"
    }
  },
  "database_user": {
    "id": "firebase_user_id",
    "created_at": "2023-01-01T00:00:00Z"
  }
}
```

### 2. 用户数据同步

系统会自动同步Firebase用户数据到本地数据库：

- **首次登录**: 自动创建数据库用户记录
- **用户信息更新**: 同步Firebase用户信息变更
- **登录时间**: 记录最后登录时间

## 开发环境配置

### 1. 跳过认证模式

在开发环境中，可以跳过Firebase认证：

```bash
# 设置环境变量
export FIREBASE_SKIP_AUTH_IN_DEV=true
export ENVIRONMENT=development
```

**注意**: 此模式仅用于开发，生产环境必须禁用。

### 2. 测试用户ID

开发模式下可以使用固定的测试用户ID：

```bash
curl -X GET "http://localhost:5001/api/user/me" \
  -H "Userid: test_user_123"
```

## 安全考虑

### 1. 令牌安全

- **令牌过期**: Firebase ID Token默认1小时过期
- **令牌刷新**: 客户端需要自动刷新过期令牌
- **令牌验证**: 服务器端验证每个请求的令牌

### 2. 服务账户密钥安全

- **密钥存储**: 使用环境变量或安全的密钥管理服务
- **权限最小化**: 服务账户仅授予必要权限
- **定期轮换**: 定期更新服务账户密钥

### 3. CORS配置

```python
# 配置CORS允许的域名
CORS_ORIGINS = [
    "http://localhost:3000",  # 开发环境
    "https://dinq.io",        # 生产环境
]
```

## 错误处理

### 1. 常见错误

#### 认证失败
```json
{
  "success": false,
  "error": "Authentication required",
  "code": "AUTH_REQUIRED"
}
```

#### 令牌无效
```json
{
  "success": false,
  "error": "Invalid token",
  "code": "INVALID_TOKEN"
}
```

#### 用户不存在
```json
{
  "success": false,
  "error": "User not found",
  "code": "USER_NOT_FOUND"
}
```

### 2. 错误日志

系统会记录详细的认证日志：

```
INFO - Successfully verified token for user: user123 (User Name, user@example.com) in 0.15s
WARNING - Failed to verify Firebase token: Token expired
ERROR - Firebase service account file not found at: /path/to/key.json
```

## 测试

### 1. 认证测试

#### 测试脚本位置
```
tests/auth_tests/
├── test_firebase_user_validation.py  # Firebase用户验证测试
└── test_auth_decorators.py          # 认证装饰器测试
```

#### 运行测试
```bash
# 测试Firebase用户验证
python tests/auth_tests/test_firebase_user_validation.py

# 测试认证装饰器
python tests/auth_tests/test_auth_decorators.py
```

### 2. 手动测试

#### 测试认证端点
```bash
# 测试无认证访问（应该失败）
curl -X GET "http://localhost:5001/api/user/me"

# 测试有效令牌访问（应该成功）
curl -X GET "http://localhost:5001/api/user/me" \
  -H "Authorization: Bearer VALID_TOKEN"

# 测试用户ID访问（开发环境）
curl -X GET "http://localhost:5001/api/user/me" \
  -H "Userid: test_user_123"
```

## 部署配置

### 1. 生产环境

#### 环境变量设置
```bash
# 生产环境配置
export ENVIRONMENT=production
export FIREBASE_SKIP_AUTH_IN_DEV=false
export FIREBASE_SERVICE_ACCOUNT_PATH=/secure/path/to/service-account-key.json
```

#### Docker配置
```dockerfile
# Dockerfile
ENV ENVIRONMENT=production
ENV FIREBASE_SKIP_AUTH_IN_DEV=false
COPY service-account-key.json /app/secrets/
ENV FIREBASE_SERVICE_ACCOUNT_PATH=/app/secrets/service-account-key.json
```

### 2. 监控和日志

#### 认证指标监控
- 认证成功率
- 令牌验证时间
- 认证失败原因分布

#### 日志配置
```python
# 配置认证相关日志
logging.getLogger('server.config.firebase_config').setLevel(logging.INFO)
logging.getLogger('server.utils.auth').setLevel(logging.INFO)
logging.getLogger('server.api.user').setLevel(logging.INFO)
```

## 故障排除

### 1. 常见问题

#### Firebase初始化失败
**问题**: `Firebase authentication is not available`
**解决**: 检查服务账户密钥路径和权限

#### 令牌验证失败
**问题**: `Failed to verify Firebase token`
**解决**: 检查令牌是否过期，客户端是否正确获取令牌

#### 用户ID不匹配
**问题**: 用户ID在Firebase中不存在
**解决**: 确保用户已在Firebase中注册

### 2. 调试方法

#### 启用详细日志
```python
import logging
logging.getLogger('server.config.firebase_config').setLevel(logging.DEBUG)
logging.getLogger('server.utils.auth').setLevel(logging.DEBUG)
```

#### 检查Firebase连接
```python
from server.config.firebase_config import firebase_initialized, firebase_auth

print(f"Firebase initialized: {firebase_initialized}")
if firebase_auth:
    print("Firebase auth available")
else:
    print("Firebase auth not available")
```

## 最佳实践

### 1. 客户端集成

#### JavaScript/React示例
```javascript
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';

// 登录并获取ID Token
const auth = getAuth();
const userCredential = await signInWithEmailAndPassword(auth, email, password);
const idToken = await userCredential.user.getIdToken();

// 使用ID Token调用API
const response = await fetch('/api/user/me', {
  headers: {
    'Authorization': `Bearer ${idToken}`,
    'Content-Type': 'application/json'
  }
});
```

#### 令牌刷新
```javascript
// 自动刷新令牌
auth.onIdTokenChanged(async (user) => {
  if (user) {
    const token = await user.getIdToken();
    // 更新API请求头中的令牌
    updateAuthToken(token);
  }
});
```

### 2. 服务器端最佳实践

#### 缓存用户信息
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_user_info(user_id: str):
    """缓存用户信息以提高性能"""
    return firebase_auth.get_user(user_id)
```

#### 批量用户验证
```python
def verify_multiple_users(user_ids: list):
    """批量验证多个用户"""
    results = []
    for user_id in user_ids:
        try:
            user = firebase_auth.get_user(user_id)
            results.append({"user_id": user_id, "valid": True})
        except:
            results.append({"user_id": user_id, "valid": False})
    return results
```

## 总结

Firebase认证系统为DINQ项目提供了：

1. **安全可靠的认证** - 基于行业标准的OAuth 2.0和JWT
2. **灵活的认证方式** - 支持多种登录方式（邮箱、Google、GitHub等）
3. **完整的用户管理** - 用户注册、登录、信息管理
4. **开发友好** - 开发环境支持跳过认证，便于测试
5. **生产就绪** - 完整的错误处理、日志记录和监控

通过合理配置和使用Firebase认证系统，可以确保DINQ项目的用户数据安全和系统稳定性。
