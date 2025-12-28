# GitHub 分析器流式 API 文档（SSE）

## 📋 概述

GitHub分析器流式API提供实时的GitHub用户分析功能，使用Server-Sent Events (SSE)技术实现流式输出，让前端可以实时显示分析进度和结果。

## 🌊 流式分析端点

### POST `/api/github/analyze-stream`

**描述**: 使用Server-Sent Events (SSE)实时流式分析GitHub用户，提供实时进度更新

**认证**: ✅ 必需 (需要在请求头中包含 `Userid`)

**Content-Type**: `application/json`

**Accept**: `text/event-stream`

---

## 📤 请求格式

### 请求头
```http
POST /api/github/analyze-stream HTTP/1.1
Host: localhost:5001
Content-Type: application/json
Accept: text/event-stream
Userid: your_user_id
Cache-Control: no-cache
```

### 请求体
```json
{
  "username": "octocat"
}
```

---

## 📥 响应格式

流式响应使用Server-Sent Events格式，每个消息以 `data: ` 开头，包含JSON格式的数据。

### 响应头
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Cache-Control
```

---

## 🔄 消息类型（统一 Schema）

所有流式端点已收敛到统一 schema（GitHub/Scholar/PK 复用同一套字段）：

```json
{
  "source": "github",
  "event_type": "start|progress|data|final|error|end",
  "message": "人类可读文本（可选）",
  "step": "逻辑步骤名（可选）",
  "progress": 0,
  "payload": { "任意结构化数据（可选）" },
  "type": "legacy type（可选，兼容旧前端）"
}
```

约定：
- SSE 只输出：`data: {json}\n\n`（不使用 `event:` 字段）
- `event_type=end` 必发（无论成功/失败/取消/超时）
- 错误统一为 `event_type=error`，且 `payload` 统一为 `{code,message,retryable,detail}`

### 1) 开始事件（`event_type=start`）
```json
{
  "source": "github",
  "event_type": "start",
  "step": "start",
  "message": "开始分析 GitHub 用户: octocat",
  "payload": { "username": "octocat" }
}
```

### 2) 进度事件（`event_type=progress`）
```json
{
  "source": "github",
  "event_type": "progress",
  "step": "profile_fetch",
  "message": "获取用户 octocat 的基本信息...",
  "progress": 12.5,
  "payload": { "user": "The Octocat" }
}
```

### 3) 最终结果（`event_type=final`，可选）
```json
{
  "source": "github",
  "event_type": "final",
  "step": "final",
  "message": "分析完成",
  "payload": {
    "success": true,
    "username": "octocat",
    "data": {
      "user": { /* 用户基本信息 */ },
      "overview": { /* 概览统计 */ },
      "activity": { /* 活动数据 */ },
      "feature_project": { /* 特色项目 */ },
      "code_contribution": { /* 代码贡献 */ },
      "top_projects": [ /* 贡献的顶级项目 */ ],
      "valuation_and_level": { /* AI评估结果 */ },
      "role_model": { /* 角色模型匹配 */ },
      "roast": "/* AI生成的评价 */"
    }
  }
}
```

### 4) 错误事件（`event_type=error`）
```json
{
  "source": "github",
  "event_type": "error",
  "step": "analyze_error",
  "message": "错误描述",
  "payload": {
    "code": "internal_error",
    "message": "错误描述",
    "retryable": false,
    "detail": { "任意结构化错误信息": true }
  }
}
```

### 5) 结束事件（`event_type=end`，必发）
```json
{
  "source": "github",
  "event_type": "end"
}
```

---

## 📊 进度步骤详解

| 步骤 | 描述 | 预计耗时 |
|------|------|----------|
| `usage_check` | 检查使用限制 | < 1s |
| `init_analyzer` | 初始化分析器 | < 1s |
| `check_cache` | 检查缓存 | < 1s |
| `cache_found` | 找到缓存结果 | < 1s |
| `cache_invalid` | 缓存数据损坏 | < 1s |
| `profile_fetch` | 获取用户基本信息 | 2-5s |
| `profile_success` | 用户信息获取成功 | - |
| `parse_datetime` | 解析用户创建时间 | < 1s |
| `datetime_success` | 时间解析成功 | - |
| `work_exp_calculated` | 计算工作经验 | < 1s |
| `data_collection_start` | 开始数据收集 | - |
| `pull_requests_start` | 获取Pull Requests数据 | 3-8s |
| `pull_requests_success` | PR数据获取成功 | - |
| `mutations_start` | 获取代码变更统计 | 3-8s |
| `mutations_success` | 代码统计获取成功 | - |
| `activity_start` | 获取活动数据 | 2-5s |
| `activity_success` | 活动数据获取成功 | - |
| `starred_repos_start` | 获取热门仓库 | 2-5s |
| `starred_repos_success` | 热门仓库获取成功 | - |
| `contributed_repos_start` | 获取贡献仓库 | 3-8s |
| `contributed_repos_success` | 贡献仓库获取成功 | - |
| `data_collection_complete` | 数据收集完成 | - |
| `calculating_stats` | 计算统计数据 | 1-2s |
| `overview_complete` | 基础统计完成 | - |
| `feature_project_start` | 分析特色项目 | 2-5s |
| `feature_project_success` | 特色项目分析完成 | - |
| `ai_analysis_start` | 开始AI分析 | - |
| `ai_user_tags_start` | 生成用户技能标签 | 5-15s |
| `ai_basic_complete` | AI基础分析完成 | - |
| `ai_advanced_start` | 进行高级AI分析 | - |
| `ai_analysis_complete` | AI分析完成 | 10-30s |
| `saving_cache` | 保存到缓存 | 1-2s |
| `cache_saved` | 缓存保存完成 | - |
| `analysis_complete` | 分析完成 | - |

**总预计时间**: 30-90秒（取决于GitHub API响应速度和AI分析复杂度）
