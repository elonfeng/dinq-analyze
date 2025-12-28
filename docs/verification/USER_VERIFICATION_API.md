# User Verification API Documentation

这个API提供了完整的用户验证系统，支持求职者和招聘方的分步骤验证流程。

## 认证

所有API端点都需要用户认证。请在请求头中包含以下字段：

```
Userid: <user_id>
```

或

```
userid: <user_id>
```

## 用户类型

系统支持两种用户类型：

- `job_seeker`: 寻找机会的人（求职者）
- `recruiter`: 招聘方

## 验证步骤

### 求职者验证流程

1. **Basic Information** (`basic_info`)
   - Full name (必需)
   - 头像 (可选)
   - 当前角色 (必需)
   - 当前title (必需)
   - 研究领域 (可选)

2. **Education** (`education`)
   - 大学名称 (必需)
   - Degree level (必需)
   - Department/major (必需)
   - 教育邮箱 (必需，需要验证)
   - 文档上传 (可选)

3. **Professional** (`professional`)
   - Job title (必需)
   - Company/org (必需)
   - Work/research summary (必需)
   - 公司邮箱 (可选，需要验证)
   - 文档上传 (可选)

4. **Social Accounts** (`social_accounts`)
   - GitHub (可选)
   - LinkedIn (可选)
   - Twitter/X (可选)

### 招聘方验证流程

1. **Basic Information** (`basic_info`)
   - Full name (必需)
   - 头像 (可选)
   - Current role (必需)
   - Current title (必需)

2. **Company/Organization** (`company_org`)
   - Company name (必需)
   - Industry (必需)
   - 公司邮箱 (必需，需要验证)
   - Website (可选)
   - Introduction (可选)
   - 文档上传 (可选)

3. **Social Accounts** (`social_accounts`)
   - GitHub (可选)
   - LinkedIn (可选)
   - Twitter/X (可选)
   - Google Scholar (可选)

## API 端点

### 1. 获取验证状态

**端点**: `GET /api/verification/status`

**描述**: 获取当前用户的验证状态

**示例请求**:
```bash
curl -X GET http://localhost:5001/api/verification/status \
  -H "Userid: user123"
```

**成功响应** (200):
```json
{
  "success": true,
  "data": {
    "exists": true,
    "verification": {
      "id": 1,
      "user_id": "user123",
      "user_type": "job_seeker",
      "current_step": "education",
      "verification_status": "pending",
      "full_name": "John Doe",
      "current_role": "Researcher",
      "current_title": "PhD Student",
      "research_fields": ["Machine Learning", "Computer Vision"],
      "university_name": "Stanford University",
      "degree_level": "PhD",
      "department_major": "Computer Science",
      "edu_email": "john@stanford.edu",
      "edu_email_verified": true,
      "created_at": "2023-12-01T10:00:00Z",
      "updated_at": "2023-12-01T10:30:00Z"
    },
    "email_verification_statuses": {
      "edu_email": true,
      "company_email": false
    }
  }
}
```

### 2. 开始验证流程

**端点**: `POST /api/verification/start`

**描述**: 开始用户验证流程

**请求格式**: `application/json`

**参数**:
- `user_type` (必需): 用户类型 (`job_seeker` 或 `recruiter`)

**示例请求**:
```bash
curl -X POST http://localhost:5001/api/verification/start \
  -H "Userid: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "user_type": "job_seeker"
  }'
```

**成功响应** (201):
```json
{
  "success": true,
  "data": {
    "verification": {
      "id": 1,
      "user_id": "user123",
      "user_type": "job_seeker",
      "current_step": "basic_info",
      "verification_status": "pending",
      "created_at": "2023-12-01T10:00:00Z",
      "updated_at": "2023-12-01T10:00:00Z"
    },
    "message": "Verification process started successfully."
  }
}
```

### 3. 更新验证步骤

**端点**: `POST /api/verification/update-step`

**描述**: 更新验证步骤数据

**请求格式**: `application/json`

**参数**:
- `step` (必需): 当前步骤名称
- `data` (必需): 步骤数据
- `advance_to_next` (可选): 是否自动进入下一步，默认false

**示例请求** (基本信息):
```bash
curl -X POST http://localhost:5001/api/verification/update-step \
  -H "Userid: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "basic_info",
    "data": {
      "full_name": "John Doe",
      "current_role": "Researcher",
      "current_title": "PhD Student",
      "research_fields": ["Machine Learning", "Computer Vision"]
    },
    "advance_to_next": true
  }'
```

**示例请求** (教育信息):
```bash
curl -X POST http://localhost:5001/api/verification/update-step \
  -H "Userid: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "education",
    "data": {
      "university_name": "Stanford University",
      "degree_level": "PhD",
      "department_major": "Computer Science",
      "edu_email": "john@stanford.edu",
      "education_documents": ["doc1.pdf", "doc2.pdf"]
    },
    "advance_to_next": true
  }'
```

**成功响应** (200):
```json
{
  "success": true,
  "data": {
    "verification": {
      "id": 1,
      "user_id": "user123",
      "user_type": "job_seeker",
      "current_step": "education",
      "verification_status": "pending",
      "full_name": "John Doe",
      "current_role": "Researcher",
      "current_title": "PhD Student",
      "research_fields": ["Machine Learning", "Computer Vision"],
      "updated_at": "2023-12-01T10:30:00Z"
    },
    "message": "Step updated successfully."
  }
}
```

### 4. 发送邮箱验证码

**端点**: `POST /api/verification/send-email-verification`

**描述**: 发送邮箱验证码

**请求格式**: `application/json`

**参数**:
- `email` (必需): 要验证的邮箱地址
- `email_type` (必需): 邮箱类型 (`edu_email`, `company_email`, `recruiter_company_email`)

**示例请求**:
```bash
curl -X POST http://localhost:5001/api/verification/send-email-verification \
  -H "Userid: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@stanford.edu",
    "email_type": "edu_email"
  }'
```

**成功响应** (200):
```json
{
  "success": true,
  "data": {
    "message": "Verification email sent successfully.",
    "email": "john@stanford.edu",
    "email_type": "edu_email"
  }
}
```

### 5. 验证邮箱

**端点**: `POST /api/verification/verify-email`

**描述**: 使用验证码验证邮箱

**请求格式**: `application/json`

**参数**:
- `email` (必需): 邮箱地址
- `email_type` (必需): 邮箱类型
- `verification_code` (必需): 6位验证码

**示例请求**:
```bash
curl -X POST http://localhost:5001/api/verification/verify-email \
  -H "Userid: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@stanford.edu",
    "email_type": "edu_email",
    "verification_code": "123456"
  }'
```

**成功响应** (200):
```json
{
  "success": true,
  "data": {
    "message": "Email verified successfully.",
    "email": "john@stanford.edu",
    "email_type": "edu_email",
    "verified": true
  }
}
```

### 6. 完成验证

**端点**: `POST /api/verification/complete`

**描述**: 完成整个验证流程

**示例请求**:
```bash
curl -X POST http://localhost:5001/api/verification/complete \
  -H "Userid: user123"
```

**成功响应** (200):
```json
{
  "success": true,
  "data": {
    "verification": {
      "id": 1,
      "user_id": "user123",
      "user_type": "job_seeker",
      "current_step": "completed",
      "verification_status": "verified",
      "completed_at": "2023-12-01T11:00:00Z",
      "updated_at": "2023-12-01T11:00:00Z"
    },
    "message": "Verification completed successfully!"
  }
}
```

### 7. 获取验证统计

**端点**: `GET /api/verification/stats`

**描述**: 获取验证统计信息（管理员端点）

**示例请求**:
```bash
curl -X GET http://localhost:5001/api/verification/stats
```

**成功响应** (200):
```json
{
  "success": true,
  "data": {
    "stats_by_type": [
      {
        "user_type": "job_seeker",
        "verification_status": "pending",
        "count": 15
      },
      {
        "user_type": "job_seeker",
        "verification_status": "verified",
        "count": 8
      },
      {
        "user_type": "recruiter",
        "verification_status": "pending",
        "count": 5
      },
      {
        "user_type": "recruiter",
        "verification_status": "verified",
        "count": 3
      }
    ],
    "step_distribution": [
      {
        "step": "basic_info",
        "count": 10
      },
      {
        "step": "education",
        "count": 8
      },
      {
        "step": "professional",
        "count": 5
      },
      {
        "step": "completed",
        "count": 11
      }
    ]
  }
}
```

## 邮箱验证流程

1. **发送验证码**: 调用 `/send-email-verification` 端点
2. **用户收到邮件**: 包含6位数字验证码，有效期15分钟
3. **验证邮箱**: 调用 `/verify-email` 端点提交验证码
4. **更新状态**: 验证成功后，对应的邮箱验证状态会更新

## 验证码特性

- **格式**: 6位数字
- **有效期**: 15分钟
- **重试次数**: 最多3次
- **安全性**: 每次发送新验证码会使旧验证码失效

## 错误代码

- `400 Bad Request`: 请求参数错误或验证失败
- `404 Not Found`: 验证记录不存在
- `500 Internal Server Error`: 服务器内部错误

## 前端集成示例

### JavaScript/React示例

```javascript
class VerificationService {
  constructor(baseURL, userId) {
    this.baseURL = baseURL;
    this.userId = userId;
  }

  async startVerification(userType) {
    const response = await fetch(`${this.baseURL}/api/verification/start`, {
      method: 'POST',
      headers: {
        'Userid': this.userId,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ user_type: userType })
    });
    return await response.json();
  }

  async updateStep(step, data, advanceToNext = false) {
    const response = await fetch(`${this.baseURL}/api/verification/update-step`, {
      method: 'POST',
      headers: {
        'Userid': this.userId,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        step,
        data,
        advance_to_next: advanceToNext
      })
    });
    return await response.json();
  }

  async sendEmailVerification(email, emailType) {
    const response = await fetch(`${this.baseURL}/api/verification/send-email-verification`, {
      method: 'POST',
      headers: {
        'Userid': this.userId,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email,
        email_type: emailType
      })
    });
    return await response.json();
  }

  async verifyEmail(email, emailType, verificationCode) {
    const response = await fetch(`${this.baseURL}/api/verification/verify-email`, {
      method: 'POST',
      headers: {
        'Userid': this.userId,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email,
        email_type: emailType,
        verification_code: verificationCode
      })
    });
    return await response.json();
  }

  async getStatus() {
    const response = await fetch(`${this.baseURL}/api/verification/status`, {
      headers: {
        'Userid': this.userId
      }
    });
    return await response.json();
  }

  async completeVerification() {
    const response = await fetch(`${this.baseURL}/api/verification/complete`, {
      method: 'POST',
      headers: {
        'Userid': this.userId
      }
    });
    return await response.json();
  }
}

// 使用示例
const verificationService = new VerificationService('http://localhost:5001', 'user123');

// 开始验证
await verificationService.startVerification('job_seeker');

// 更新基本信息
await verificationService.updateStep('basic_info', {
  full_name: 'John Doe',
  current_role: 'Researcher',
  current_title: 'PhD Student'
}, true);

// 发送邮箱验证
await verificationService.sendEmailVerification('john@stanford.edu', 'edu_email');

// 验证邮箱
await verificationService.verifyEmail('john@stanford.edu', 'edu_email', '123456');
```

## 注意事项

1. **数据验证**: 每个步骤都有必需字段验证
2. **邮箱验证**: 教育邮箱和公司邮箱需要通过验证码验证
3. **步骤顺序**: 建议按照定义的步骤顺序进行验证
4. **文件上传**: 文档上传需要先使用图片上传API上传文件，然后将URL保存到验证记录中
5. **社交账号验证**: 目前社交账号验证是可选的，未来可能会添加OAuth验证
