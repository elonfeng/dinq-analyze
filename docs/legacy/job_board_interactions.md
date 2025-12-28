# Job Board 用户交互功能

本文档介绍了Job Board的用户交互功能，包括点赞和收藏功能。

## 功能概述

Job Board用户交互功能允许用户：

1. **点赞职位帖子**：用户可以点赞感兴趣的职位帖子，表示对该职位的兴趣或支持。
2. **收藏职位帖子**：用户可以收藏感兴趣的职位帖子，方便后续查看。
3. **添加收藏备注**：用户可以为收藏的职位帖子添加个人备注，记录对该职位的想法或计划。
4. **查看交互状态**：用户可以查看自己与帖子的交互状态，包括是否已点赞、是否已收藏等。
5. **查看点赞/收藏列表**：用户可以查看自己点赞或收藏的所有职位帖子。

## 数据库模型

### JobPostLike

记录用户对职位帖子的点赞。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | String | 用户ID |
| post_id | Integer | 帖子ID |
| created_at | DateTime | 点赞时间 |

### JobPostBookmark

记录用户对职位帖子的收藏。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | String | 用户ID |
| post_id | Integer | 帖子ID |
| notes | String | 收藏备注 |
| created_at | DateTime | 收藏时间 |
| updated_at | DateTime | 更新时间 |

## API接口

### 点赞相关接口

#### 点赞帖子

```
POST /api/job-board/posts/{post_id}/like
```

**请求头**：
- `Userid`: 用户ID

**响应**：
```json
{
  "success": true,
  "message": "Post liked successfully",
  "data": {
    "post_id": 123,
    "like_count": 10,
    "is_liked": true
  }
}
```

#### 取消点赞

```
DELETE /api/job-board/posts/{post_id}/like
```

**请求头**：
- `Userid`: 用户ID

**响应**：
```json
{
  "success": true,
  "message": "Post unliked successfully",
  "data": {
    "post_id": 123,
    "like_count": 9,
    "is_liked": false
  }
}
```

#### 获取用户点赞的帖子

```
GET /api/job-board/my-liked-posts?limit=20&offset=0
```

**请求头**：
- `Userid`: 用户ID

**响应**：
```json
{
  "success": true,
  "data": {
    "posts": [
      {
        "id": 123,
        "title": "测试职位",
        "content": "这是一个测试职位",
        "post_type": "job_offer",
        "location": "测试城市",
        "company": "测试公司",
        "position": "测试职位",
        "tags": ["测试", "点赞", "收藏"],
        "is_active": true,
        "view_count": 100,
        "created_at": "2025-04-15T12:00:00",
        "updated_at": "2025-04-15T12:00:00",
        "like_count": 10
      }
    ],
    "pagination": {
      "limit": 20,
      "offset": 0
    }
  }
}
```

### 收藏相关接口

#### 收藏帖子

```
POST /api/job-board/posts/{post_id}/bookmark
```

**请求头**：
- `Userid`: 用户ID

**请求体**：
```json
{
  "notes": "这个职位很适合我"
}
```

**响应**：
```json
{
  "success": true,
  "message": "Post bookmarked successfully",
  "data": {
    "post_id": 123,
    "is_bookmarked": true,
    "notes": "这个职位很适合我"
  }
}
```

#### 取消收藏

```
DELETE /api/job-board/posts/{post_id}/bookmark
```

**请求头**：
- `Userid`: 用户ID

**响应**：
```json
{
  "success": true,
  "message": "Bookmark removed successfully",
  "data": {
    "post_id": 123,
    "is_bookmarked": false
  }
}
```

#### 更新收藏备注

```
PUT /api/job-board/posts/{post_id}/bookmark/notes
```

**请求头**：
- `Userid`: 用户ID

**请求体**：
```json
{
  "notes": "更新后的备注：这个职位非常适合我"
}
```

**响应**：
```json
{
  "success": true,
  "message": "Bookmark notes updated successfully",
  "data": {
    "post_id": 123,
    "notes": "更新后的备注：这个职位非常适合我"
  }
}
```

#### 获取用户收藏的帖子

```
GET /api/job-board/my-bookmarked-posts?limit=20&offset=0
```

**请求头**：
- `Userid`: 用户ID

**响应**：
```json
{
  "success": true,
  "data": {
    "posts": [
      {
        "id": 123,
        "title": "测试职位",
        "content": "这是一个测试职位",
        "post_type": "job_offer",
        "location": "测试城市",
        "company": "测试公司",
        "position": "测试职位",
        "tags": ["测试", "点赞", "收藏"],
        "is_active": true,
        "view_count": 100,
        "created_at": "2025-04-15T12:00:00",
        "updated_at": "2025-04-15T12:00:00",
        "bookmark": {
          "id": 456,
          "notes": "这个职位很适合我",
          "created_at": "2025-04-15T12:30:00",
          "updated_at": "2025-04-15T12:30:00"
        }
      }
    ],
    "pagination": {
      "total": 1,
      "limit": 20,
      "offset": 0,
      "has_more": false
    }
  }
}
```

### 交互状态接口

#### 获取帖子交互状态

```
GET /api/job-board/posts/{post_id}/status
```

**请求头**：
- `Userid`: 用户ID

**响应**：
```json
{
  "success": true,
  "data": {
    "post_id": 123,
    "is_liked": true,
    "is_bookmarked": true,
    "like_count": 10
  }
}
```

## 使用示例

### 前端示例

```javascript
// 点赞帖子
async function likePost(postId) {
  const response = await fetch(`/api/job-board/posts/${postId}/like`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Userid': 'current-user-id'
    }
  });
  const result = await response.json();
  if (result.success) {
    console.log(`帖子点赞成功，当前点赞数: ${result.data.like_count}`);
  }
}

// 收藏帖子
async function bookmarkPost(postId, notes) {
  const response = await fetch(`/api/job-board/posts/${postId}/bookmark`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Userid': 'current-user-id'
    },
    body: JSON.stringify({ notes })
  });
  const result = await response.json();
  if (result.success) {
    console.log(`帖子收藏成功，备注: ${result.data.notes}`);
  }
}
```

### 后端测试

可以使用提供的测试脚本验证API接口功能：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行API测试
python tests/api_tests/test_job_board_interactions_api.py
```

## 初始化数据库表

在使用这些功能前，需要确保数据库表已经创建：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 初始化数据库表
python tools/init_user_interactions_tables.py
```
