# Job Board API 接口文档

本文档描述了 Job Board API 的接口规范，包括请求方法、URL、参数、请求体和响应格式。

## 基本信息

- **基础URL**: `http://qingke.aihe.space` (开发环境) 或 `https://your-production-domain.com` (生产环境)
- **认证方式**: 通过请求头中的 `Userid` 或 `userid` 字段提供用户ID，或通过 `Authorization: Bearer {token}` 提供 Firebase 令牌
- **验证用户**: 某些端点（如创建帖子）需要经过 Firebase 验证的真实用户
- **响应格式**: 所有API响应均为JSON格式
- **日期格式**: ISO 8601 格式 (例如: `2023-04-15T08:49:27`)
- **错误处理**: 当发生错误时，API将返回相应的HTTP状态码和错误信息

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

## 认证

所有需要认证的接口都需要在请求头中包含用户ID或令牌:

### 方式1: 用户ID头

```
Userid: your-user-id
```

或者:

```
userid: your-user-id
```

### 方式2: Bearer 令牌

```
Authorization: Bearer your-firebase-token
```

## 验证用户

某些端点（如创建帖子）需要经过 Firebase 验证的真实用户。这些端点使用更严格的验证方式，即使在开发环境中也不允许未经验证的用户访问。

这些端点包括:

- `POST /api/job-board/posts` (创建新的职位发布)

## API 端点

### 1. 获取职位发布列表

获取职位发布列表，支持筛选和分页。

- **URL**: `/api/job-board/posts`
- **方法**: `GET`
- **认证**: 可选
- **查询参数**:
  - `limit`: 每页返回的最大记录数 (默认: 20)
  - `offset`: 跳过的记录数 (默认: 0)
  - `post_type`: 按发布类型筛选 (可选值: `job_offer`, `job_seeking`, `announcement`, `other`)
  - `location`: 按地点筛选
  - `company`: 按公司筛选
  - `position`: 按职位筛选
  - `search`: 在标题和内容中搜索
  - `user_id`: 按用户ID筛选
  - `tags`: 按标签筛选 (逗号分隔)
  - `sort_by`: 排序字段 (默认: `created_at`)
  - `sort_order`: 排序顺序 (可选值: `asc`, `desc`, 默认: `desc`)

#### 请求示例

```
GET /api/job-board/posts?limit=10&offset=0&post_type=job_offer&location=北京&search=工程师&sort_by=created_at&sort_order=desc
```

#### 响应示例

```json
{
  "success": true,
  "data": {
    "posts": [
      {
        "id": 1,
        "user_id": "user123",
        "title": "招聘高级前端工程师",
        "content": "我们正在寻找有经验的前端工程师...",
        "post_type": "job_offer",
        "location": "北京",
        "company": "ABC科技有限公司",
        "position": "高级前端工程师",
        "salary_range": "25k-35k",
        "contact_info": "hr@example.com",
        "tags": ["JavaScript", "React", "Vue"],
        "is_active": true,
        "view_count": 42,
        "created_at": "2023-04-15T08:49:27",
        "updated_at": "2023-04-15T08:49:27"
      },
      // 更多职位发布...
    ],
    "pagination": {
      "total": 42,
      "limit": 10,
      "offset": 0,
      "has_more": true
    }
  }
}
```

### 2. 获取单个职位发布

获取单个职位发布的详细信息。

- **URL**: `/api/job-board/posts/{post_id}`
- **方法**: `GET`
- **认证**: 可选
- **URL参数**:
  - `post_id`: 职位发布ID

#### 请求示例

```
GET /api/job-board/posts/1
```

#### 响应示例

```json
{
  "success": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "title": "招聘高级前端工程师",
    "content": "我们正在寻找有经验的前端工程师...",
    "post_type": "job_offer",
    "location": "北京",
    "company": "ABC科技有限公司",
    "position": "高级前端工程师",
    "salary_range": "25k-35k",
    "contact_info": "hr@example.com",
    "tags": ["JavaScript", "React", "Vue"],
    "is_active": true,
    "view_count": 43,
    "created_at": "2023-04-15T08:49:27",
    "updated_at": "2023-04-15T08:49:27"
  }
}
```

### 3. 创建职位发布

创建新的职位发布。

- **URL**: `/api/job-board/posts`
- **方法**: `POST`
- **认证**: 必需（需要经过验证的真实用户）
- **请求体**:
  - `title`: 标题 (必需)
  - `content`: 内容 (必需)
  - `post_type`: 发布类型 (可选值: `job_offer`, `job_seeking`, `announcement`, `other`, 默认: `job_offer`)
  - `location`: 地点 (可选)
  - `company`: 公司 (可选)
  - `position`: 职位 (可选)
  - `salary_range`: 薪资范围 (可选)
  - `contact_info`: 联系方式 (可选)
  - `tags`: 标签数组 (可选)

#### 请求示例

```json
POST /api/job-board/posts
Content-Type: application/json
Userid: user123

{
  "title": "招聘高级前端工程师",
  "content": "我们正在寻找有经验的前端工程师...",
  "post_type": "job_offer",
  "location": "北京",
  "company": "ABC科技有限公司",
  "position": "高级前端工程师",
  "salary_range": "25k-35k",
  "contact_info": "hr@example.com",
  "tags": ["JavaScript", "React", "Vue"]
}
```

#### 响应示例

```json
{
  "success": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "title": "招聘高级前端工程师",
    "content": "我们正在寻找有经验的前端工程师...",
    "post_type": "job_offer",
    "location": "北京",
    "company": "ABC科技有限公司",
    "position": "高级前端工程师",
    "salary_range": "25k-35k",
    "contact_info": "hr@example.com",
    "tags": ["JavaScript", "React", "Vue"],
    "is_active": true,
    "view_count": 0,
    "created_at": "2023-04-15T08:49:27",
    "updated_at": "2023-04-15T08:49:27"
  }
}
```

### 4. 更新职位发布

更新现有的职位发布。

- **URL**: `/api/job-board/posts/{post_id}`
- **方法**: `PUT`
- **认证**: 必需 (只有创建者可以更新)
- **URL参数**:
  - `post_id`: 职位发布ID
- **请求体**: 与创建职位发布相同，但所有字段都是可选的

#### 请求示例

```json
PUT /api/job-board/posts/1
Content-Type: application/json
Userid: user123

{
  "title": "招聘资深前端工程师",
  "salary_range": "30k-40k",
  "tags": ["JavaScript", "React", "Vue", "TypeScript"]
}
```

#### 响应示例

```json
{
  "success": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "title": "招聘资深前端工程师",
    "content": "我们正在寻找有经验的前端工程师...",
    "post_type": "job_offer",
    "location": "北京",
    "company": "ABC科技有限公司",
    "position": "高级前端工程师",
    "salary_range": "30k-40k",
    "contact_info": "hr@example.com",
    "tags": ["JavaScript", "React", "Vue", "TypeScript"],
    "is_active": true,
    "view_count": 43,
    "created_at": "2023-04-15T08:49:27",
    "updated_at": "2023-04-15T09:15:42"
  }
}
```

### 5. 删除职位发布

删除职位发布。

- **URL**: `/api/job-board/posts/{post_id}`
- **方法**: `DELETE`
- **认证**: 必需 (只有创建者可以删除)
- **URL参数**:
  - `post_id`: 职位发布ID

#### 请求示例

```
DELETE /api/job-board/posts/1
Userid: user123
```

#### 响应示例

```json
{
  "success": true,
  "message": "Post deleted successfully"
}
```

### 6. 获取当前用户的职位发布

获取当前认证用户创建的职位发布列表。

- **URL**: `/api/job-board/my-posts`
- **方法**: `GET`
- **认证**: 必需
- **查询参数**: 与获取职位发布列表相同

#### 请求示例

```
GET /api/job-board/my-posts?limit=10&offset=0&sort_by=created_at&sort_order=desc
Userid: user123
```

#### 响应示例

```json
{
  "success": true,
  "data": {
    "posts": [
      {
        "id": 1,
        "user_id": "user123",
        "title": "招聘资深前端工程师",
        "content": "我们正在寻找有经验的前端工程师...",
        "post_type": "job_offer",
        "location": "北京",
        "company": "ABC科技有限公司",
        "position": "高级前端工程师",
        "salary_range": "30k-40k",
        "contact_info": "hr@example.com",
        "tags": ["JavaScript", "React", "Vue", "TypeScript"],
        "is_active": true,
        "view_count": 43,
        "created_at": "2023-04-15T08:49:27",
        "updated_at": "2023-04-15T09:15:42"
      },
      // 更多职位发布...
    ],
    "pagination": {
      "total": 5,
      "limit": 10,
      "offset": 0,
      "has_more": false
    }
  }
}
```

## 错误码

| HTTP 状态码 | 描述 |
|------------|------|
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 示例错误响应

```json
{
  "success": false,
  "error": "Post not found"
}
```

```json
{
  "success": false,
  "error": "You are not authorized to update this post"
}
```

```json
{
  "success": false,
  "error": "Title is required"
}
```

## 注意事项

1. 所有需要认证的接口都必须在请求头中包含用户ID
2. 只有创建者可以更新或删除职位发布
3. 在生产环境中，所有API请求都应该通过HTTPS进行
4. 日期字段使用ISO 8601格式
5. 标签字段是字符串数组

## 测试页面

您可以通过访问以下URL来测试Job Board API:

```
http://localhost:5001/sub_html/job_board.html
```

这个页面提供了一个简单的用户界面，可以用来创建、查看、更新和删除职位发布。

## 相关API

- [Demo Request API 文档](./demo_request_api.md) - 产品演示请求API文档
