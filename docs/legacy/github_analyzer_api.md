# GitHub分析器 API 文档

## 📋 概述

GitHub分析器API为DINQ项目提供深度的GitHub用户分析功能，包括代码贡献分析、技能评估、薪资估算、角色匹配等。本文档面向前端开发者，详细说明如何调用这些API接口。

## 🔗 基础信息

- **Base URL**: `http://localhost:5001` (开发环境) / `https://your-domain.com` (生产环境)
- **API前缀**: `/api/github`
- **认证方式**: Header中的`Userid`字段
- **内容类型**: `application/json`

## 🔐 认证要求

所有需要认证的接口都需要在请求头中包含用户ID：

```javascript
headers: {
  'Userid': 'your_user_id_here',
  'Content-Type': 'application/json'
}
```

## 📚 API 端点详情

### 1. 流式分析GitHub用户 (推荐)

#### POST `/api/github/analyze-stream`

**描述**: 使用Server-Sent Events (SSE)实时流式分析GitHub用户，提供实时进度更新

**认证**: ✅ 必需

**请求示例**:
```javascript
// 使用EventSource (推荐)
const eventSource = new EventSource('/api/github/analyze-stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Userid': 'your_user_id'
  },
  body: JSON.stringify({
    username: 'octocat'
  })
});

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);

  switch(data.type) {
    case 'start':
      console.log('分析开始:', data.message);
      break;
    case 'progress':
      console.log('进度更新:', data.message);
      updateProgressBar(data.step);
      break;
    case 'complete':
      console.log('分析完成:', data.data);
      eventSource.close();
      break;
    case 'error':
      console.error('分析错误:', data.error);
      eventSource.close();
      break;
  }
};

// 使用fetch (备选)
const response = await fetch('/api/github/analyze-stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Userid': 'your_user_id'
  },
  body: JSON.stringify({
    username: 'octocat'
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      handleStreamData(data);
    }
  }
}
```

**流式消息类型**:

1. **start** - 分析开始
```json
{
  "type": "start",
  "message": "开始分析GitHub用户: octocat",
  "username": "octocat"
}
```

2. **progress** - 进度更新
```json
{
  "type": "progress",
  "step": "profile_fetch",
  "message": "获取用户 octocat 的基本信息...",
  "data": {"user": "The Octocat"}
}
```

3. **complete** - 分析完成
```json
{
  "type": "complete",
  "success": true,
  "username": "octocat",
  "data": {
    // 完整的分析结果
  },
  "from_cache": false,
  "usage_info": {
    "remaining_uses": 9,
    "total_usage": 1
  }
}
```

4. **error** - 错误信息
```json
{
  "type": "error",
  "error": "GitHub用户不存在",
  "details": "详细错误信息"
}
```

5. **heartbeat** - 心跳消息
```json
{
  "type": "heartbeat",
  "timestamp": 1640995200.123
}
```

**进度步骤说明**:
- `usage_check` - 检查使用限制
- `init_analyzer` - 初始化分析器
- `check_cache` - 检查缓存
- `profile_fetch` - 获取用户基本信息
- `data_collection_start` - 开始数据收集
- `pull_requests_start/success` - Pull Requests数据
- `mutations_start/success` - 代码变更统计
- `activity_start/success` - 活动数据
- `starred_repos_start/success` - 热门仓库
- `contributed_repos_start/success` - 贡献仓库
- `calculating_stats` - 计算统计数据
- `feature_project_start` - 分析特色项目
- `ai_analysis_start` - 开始AI分析
- `ai_user_tags_start` - 生成用户技能标签
- `ai_basic_complete` - AI基础分析完成
- `ai_advanced_start` - 进行高级AI分析
- `ai_analysis_complete` - AI分析完成
- `saving_cache` - 保存到缓存
- `analysis_complete` - 分析完成

### 2. 分析GitHub用户 (传统方式)

#### POST `/api/github/analyze`

**描述**: 深度分析指定的GitHub用户

**认证**: ✅ 必需

**请求示例**:
```javascript
// 使用fetch
const response = await fetch('/api/github/analyze', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Userid': 'your_user_id'
  },
  body: JSON.stringify({
    username: 'octocat'
  })
});

const result = await response.json();
```

**请求参数**:
```typescript
interface AnalyzeRequest {
  username: string; // GitHub用户名，必需
}
```

**响应示例**:
```json
{
  "success": true,
  "username": "octocat",
  "data": {
    "user": {
      "name": "The Octocat",
      "login": "octocat",
      "avatarUrl": "https://avatars.githubusercontent.com/u/583231",
      "bio": "",
      "company": "@github",
      "location": "San Francisco",
      "createdAt": "2011-01-25T18:44:36Z",
      "tags": ["open-source collaboration", "git workflows", "developer documentation"]
    },
    "overview": {
      "work_experience": 15,
      "stars": 18140,
      "repositories": 6,
      "pull_requests": 8,
      "issues": 5,
      "additions": 894,
      "deletions": 53
    },
    "valuation_and_level": {
      "level": "L5",
      "salary_range": "$180,000 - $270,000",
      "total_compensation": "$300,000 - $450,000",
      "reasoning": "15 years of work experience, significant open source impact..."
    },
    "role_model": {
      "name": "Kenneth Reitz",
      "github": "https://github.com/kennethreitz",
      "similarity_score": 0.78,
      "reason": "Like Octocat, Kenneth Reitz focuses heavily on developer tooling..."
    },
    "feature_project": {
      "name": "Spoon-Knife",
      "nameWithOwner": "octocat/Spoon-Knife",
      "description": "This repo is for demonstration purposes only.",
      "url": "https://github.com/octocat/Spoon-Knife",
      "stargazerCount": 13032,
      "forkCount": 151297,
      "tags": ["git-tutorial", "forking-demo", "test-repository"]
    },
    "most_valuable_pull_request": {
      "title": "Create .gitignore file",
      "url": "https://github.com/violet-org/boysenberry-repo/pull/16",
      "repository": "violet-org/boysenberry-repo",
      "additions": 19,
      "deletions": 0,
      "impact": "Adds standard .gitignore file to improve repository maintenance...",
      "reason": "This PR has the most substantial code changes..."
    },
    "top_projects": [
      {
        "repository": {
          "name": "boysenberry-repo",
          "url": "https://github.com/violet-org/boysenberry-repo",
          "description": "Testing",
          "stargazerCount": 286
        },
        "pull_requests": 5
      }
    ],
    "code_contribution": {
      "total": 947,
      "languages": {
        "CSS": 497,
        "HTML": 154,
        "JavaScript": 2
      }
    },
    "activity": {
      "2025-05-28": {
        "contributions": 0,
        "pull_requests": 0,
        "issues": 0,
        "comments": 0
      }
      // ... 30天的活动数据
    },
    "roast": "Looks like The Octocat's been forking around since 2011! ..."
  },
  "usage_info": {
    "remaining_uses": 9,
    "total_usage": 1,
    "limit": 10,
    "period_days": 30
  }
}
```

#### GET `/api/github/analyze` (备选)

**描述**: 通过查询参数分析GitHub用户

**认证**: ✅ 必需

**请求示例**:
```javascript
const response = await fetch('/api/github/analyze?username=octocat', {
  headers: {
    'Userid': 'your_user_id'
  }
});
```

**查询参数**:
- `username` (string, 必需): GitHub用户名

### 2. 健康检查

#### GET `/api/github/health`

**描述**: 检查GitHub分析器服务状态

**认证**: ❌ 不需要

**请求示例**:
```javascript
const response = await fetch('/api/github/health');
const health = await response.json();
```

**响应示例**:
```json
{
  "status": "healthy",
  "service": "GitHub Analyzer",
  "version": "1.0.0"
}
```

### 3. API使用说明

#### GET `/api/github/help`

**描述**: 获取API使用说明和功能介绍

**认证**: ❌ 不需要

**请求示例**:
```javascript
const response = await fetch('/api/github/help');
const help = await response.json();
```

**响应示例**:
```json
{
  "service": "DINQ GitHub Analyzer API",
  "description": "深度分析GitHub用户的代码贡献、技能水平、项目影响力等",
  "endpoints": {
    "POST /api/github/analyze": {
      "description": "分析GitHub用户（推荐方式）",
      "authentication": "required",
      "body": {"username": "github_username"}
    }
  },
  "features": [
    "深度用户分析：代码贡献、技能标签、工作经验",
    "AI驱动分析：用户标签、项目分析、角色模型匹配"
  ],
  "usage_limits": {
    "monthly_limit": 10,
    "period_days": 30
  }
}
```

### 4. 用户使用统计

#### GET `/api/github/stats`

**描述**: 获取当前用户的GitHub分析使用统计

**认证**: ✅ 必需

**请求示例**:
```javascript
const response = await fetch('/api/github/stats', {
  headers: {
    'Userid': 'your_user_id'
  }
});
```

**响应示例**:
```json
{
  "user_id": "your_user_id",
  "github_analysis_stats": {
    "/api/github/analyze": 3
  },
  "limits": {
    "monthly_limit": 10,
    "period_days": 30
  }
}
```

## 📊 TypeScript 接口定义

```typescript
// 基础响应接口
interface BaseResponse {
  success: boolean;
  error?: string;
  message?: string;
}

// 分析请求接口
interface AnalyzeRequest {
  username: string;
}

// 用户信息接口
interface GitHubUser {
  name: string;
  login: string;
  avatarUrl: string;
  bio: string;
  company: string;
  location: string;
  createdAt: string;
  tags: string[];
  url: string;
  id: string;
  repositories: { totalCount: number };
  pullRequests: { totalCount: number };
  issues: { totalCount: number };
}

// 概览统计接口
interface Overview {
  work_experience: number;
  stars: number;
  repositories: number;
  pull_requests: number;
  issues: number;
  additions: number;
  deletions: number;
}

// 薪资评估接口
interface ValuationAndLevel {
  level: string;
  salary_range: string;
  total_compensation: string;
  reasoning: string;
}

// 角色模型接口
interface RoleModel {
  name: string;
  github: string;
  similarity_score: number;
  reason: string;
}

// 特色项目接口
interface FeatureProject {
  name: string;
  nameWithOwner: string;
  description: string;
  url: string;
  stargazerCount: number;
  forkCount: number;
  tags: string[];
  contributors: number;
  used_by: number;
  monthly_trending: number;
  owner: {
    avatarUrl: string;
  };
}

// 最有价值PR接口
interface MostValuablePR {
  title: string;
  url: string;
  repository: string;
  additions: number;
  deletions: number;
  impact: string;
  reason: string;
}

// 项目信息接口
interface ProjectInfo {
  repository: {
    name: string;
    url: string;
    description: string;
    stargazerCount: number;
    owner: {
      avatarUrl: string;
    };
  };
  pull_requests: number;
}

// 代码贡献接口
interface CodeContribution {
  total: number;
  languages: Record<string, number>;
}

// 活动数据接口
interface ActivityData {
  contributions: number;
  pull_requests: number;
  issues: number;
  comments: number;
}

// 使用信息接口
interface UsageInfo {
  remaining_uses: number | null;
  total_usage: number;
  limit: number | null;
  period_days: number;
}

// 完整分析结果接口
interface AnalyzeResponse extends BaseResponse {
  username: string;
  data: {
    user: GitHubUser;
    overview: Overview;
    valuation_and_level: ValuationAndLevel;
    role_model: RoleModel;
    feature_project: FeatureProject;
    most_valuable_pull_request: MostValuablePR;
    top_projects: ProjectInfo[];
    code_contribution: CodeContribution;
    activity: Record<string, ActivityData>;
    roast: string;
  };
  usage_info: UsageInfo;
}

// 健康检查响应接口
interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  service: string;
  version: string;
  error?: string;
}

// 统计响应接口
interface StatsResponse {
  user_id: string;
  github_analysis_stats: Record<string, number>;
  limits: {
    monthly_limit: number;
    period_days: number;
  };
}
```

## 🚨 错误处理

### 常见错误状态码

| 状态码 | 含义 | 处理建议 |
|--------|------|----------|
| 200 | 成功 | 正常处理响应数据 |
| 400 | 请求参数错误 | 检查username参数是否正确 |
| 401 | 未认证 | 检查Userid头是否设置 |
| 403 | 权限不足 | 用户未验证或无权限 |
| 404 | 用户不存在 | GitHub用户名不存在 |
| 429 | 使用限制 | 已达到月度使用限制 |
| 500 | 服务器错误 | 服务器内部错误，稍后重试 |

### 错误响应格式

```json
{
  "success": false,
  "error": "User not found",
  "message": "GitHub用户 \"nonexistent_user\" 不存在或无法访问"
}
```

### 使用限制错误

```json
{
  "success": false,
  "error": "Usage limit exceeded",
  "message": "已达到月度使用限制",
  "limit_info": {
    "current_usage": 10,
    "limit": 10,
    "period_days": 30,
    "reset_date": "2025-06-28"
  }
}
```

## 🎨 前端集成示例

### React Hook 示例

```typescript
import { useState, useCallback } from 'react';

interface UseGitHubAnalyzer {
  analyze: (username: string) => Promise<AnalyzeResponse>;
  loading: boolean;
  error: string | null;
  data: AnalyzeResponse | null;
}

export const useGitHubAnalyzer = (userId: string): UseGitHubAnalyzer => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnalyzeResponse | null>(null);

  const analyze = useCallback(async (username: string): Promise<AnalyzeResponse> => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/github/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Userid': userId
        },
        body: JSON.stringify({ username })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP ${response.status}`);
      }

      const result = await response.json();
      setData(result);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '分析失败';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [userId]);

  return { analyze, loading, error, data };
};
```

### Vue Composable 示例

```typescript
import { ref, reactive } from 'vue';

export const useGitHubAnalyzer = (userId: string) => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const data = ref<AnalyzeResponse | null>(null);

  const analyze = async (username: string): Promise<AnalyzeResponse> => {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch('/api/github/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Userid': userId
        },
        body: JSON.stringify({ username })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP ${response.status}`);
      }

      const result = await response.json();
      data.value = result;
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '分析失败';
      error.value = errorMessage;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return {
    analyze,
    loading: readonly(loading),
    error: readonly(error),
    data: readonly(data)
  };
};
```

### 使用示例组件

```typescript
// React组件示例
import React, { useState } from 'react';
import { useGitHubAnalyzer } from './hooks/useGitHubAnalyzer';

const GitHubAnalyzer: React.FC = () => {
  const [username, setUsername] = useState('');
  const { analyze, loading, error, data } = useGitHubAnalyzer('your_user_id');

  const handleAnalyze = async () => {
    if (!username.trim()) return;

    try {
      await analyze(username.trim());
    } catch (err) {
      console.error('分析失败:', err);
    }
  };

  return (
    <div className="github-analyzer">
      <div className="input-section">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="输入GitHub用户名"
          disabled={loading}
        />
        <button onClick={handleAnalyze} disabled={loading || !username.trim()}>
          {loading ? '分析中...' : '开始分析'}
        </button>
      </div>

      {error && (
        <div className="error">
          错误: {error}
        </div>
      )}

      {data && (
        <div className="results">
          <h2>{data.data.user.name} ({data.data.user.login})</h2>
          <div className="overview">
            <p>工作经验: {data.data.overview.work_experience} 年</p>
            <p>星标数: {data.data.overview.stars}</p>
            <p>薪资范围: {data.data.valuation_and_level.salary_range}</p>
          </div>
          <div className="role-model">
            <h3>角色模型匹配</h3>
            <p>{data.data.role_model.name} (相似度: {data.data.role_model.similarity_score})</p>
          </div>
        </div>
      )}
    </div>
  );
};
```

## 📈 性能优化建议

1. **缓存结果**: GitHub分析结果可以缓存，避免重复分析同一用户
2. **加载状态**: 分析过程可能需要30-120秒，需要良好的加载提示
3. **错误重试**: 网络错误时提供重试机制
4. **分页加载**: 对于大量数据（如活动记录）考虑分页显示
5. **防抖处理**: 用户输入时使用防抖避免频繁请求

## 🔒 安全注意事项

1. **用户ID验证**: 确保Userid头部正确设置
2. **输入验证**: 验证GitHub用户名格式
3. **错误信息**: 不要在前端暴露敏感的错误信息
4. **使用限制**: 向用户明确显示使用限制和剩余次数

## 📞 技术支持

如果在集成过程中遇到问题：

1. 检查API端点是否正确
2. 验证认证头部是否设置
3. 查看浏览器网络面板的错误信息
4. 参考本文档的错误处理部分
5. 联系后端开发团队获取支持

---

**祝您集成顺利！如有疑问，请随时联系开发团队。** 🚀
