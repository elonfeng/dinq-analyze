# GitHub Analyzer 使用指南

## 📦 项目概述

这是一个完整的 GitHub 用户分析工具包，已经从原始的 `scripts/analyze.py` 重构并打包成一个独立的 Flask API 服务。你可以直接将这个目录复制到任何 Flask 项目中使用。

## 🚀 快速开始

### 1. 复制项目文件

将整个 `github_analyzer` 目录复制到你的目标项目中：

```bash
cp -r github_analyzer /path/to/your/flask/project/
```

### 2. 安装依赖

```bash
cd /path/to/your/flask/project/github_analyzer
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.template .env

# 编辑配置文件
nano .env
```

填入你的 API 密钥：

```env
GITHUB_TOKEN=ghp_<YOUR_TOKEN>
OPENROUTER_API_KEY=sk-or-v1-<YOUR_KEY>
CRAWLBASE_TOKEN=<YOUR_TOKEN>
```

### 4. 启动服务

#### 方式 1: 独立运行

```bash
python run.py
```

#### 方式 2: 集成到现有 Flask 应用

```python
from flask import Flask
from github_analyzer import create_app

# 创建主应用
app = Flask(__name__)

# 创建分析器应用
analyzer_app = create_app()

# 你可以将分析器的路由注册到主应用
# 或者作为子应用挂载
```

## 🔧 API 接口

### 分析 GitHub 用户

**POST** `/api/github/analyze`

```bash
curl -X POST \
  http://localhost:5000/api/github/analyze \
  -H "Content-Type: application/json" \
  -d '{"username": "octocat"}'
```

**GET** `/api/github/analyze?username=octocat`

```bash
curl "http://localhost:5000/api/github/analyze?username=octocat"
```

### 其他端点

- `GET /api/health` - 健康检查
- `GET /api/github/analyze/help` - API 使用说明

## 📊 响应数据结构

分析结果包含以下主要部分：

```json
{
  "success": true,
  "username": "octocat",
  "data": {
    "user": {
      "id": "583231",
      "name": "The Octocat",
      "login": "octocat",
      "bio": "A great octopus masquerading as a cat",
      "tags": ["open source", "github", "collaboration"]
    },
    "overview": {
      "work_experience": 10,
      "stars": 8000,
      "issues": 150,
      "pull_requests": 300,
      "repositories": 50,
      "additions": 50000,
      "deletions": 20000
    },
    "feature_project": {
      "name": "Hello-World",
      "description": "My first repository on GitHub!",
      "stargazerCount": 8000,
      "tags": ["tutorial", "beginner", "example"]
    },
    "activity": {
      "2024-01-01": {
        "pull_requests": 2,
        "issues": 1,
        "comments": 5,
        "contributions": 8
      }
    },
    "code_contribution": {
      "total": 70000,
      "languages": {
        "JavaScript": 30000,
        "Python": 25000,
        "TypeScript": 15000
      }
    },
    "top_projects": [
      {
        "repository": {
          "name": "awesome-project",
          "url": "https://github.com/owner/awesome-project"
        },
        "pull_requests": 50
      }
    ],
    "most_valuable_pull_request": {
      "repository": "facebook/react",
      "url": "https://github.com/facebook/react/pull/12345",
      "title": "Add new feature",
      "additions": 500,
      "deletions": 100,
      "reason": "High impact contribution to popular framework",
      "impact": "Improved performance for millions of developers"
    },
    "valuation_and_level": {
      "level": "L5",
      "salary_range": "$150,000 - $220,000",
      "total_compensation": "$200,000 - $350,000",
      "reasoning": "Senior level based on experience and contributions"
    },
    "role_model": {
      "name": "Linus Torvalds",
      "github": "https://github.com/torvalds",
      "similarity_score": 0.85,
      "reason": "Similar open source leadership and system-level contributions"
    },
    "roast": "With 8000 stars and a bio about being a cat, octocat is clearly the most famous feline in tech!"
  }
}
```

## 🔧 自定义配置

### 修改 AI 模型

在 `.env` 文件中设置：

```env
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
# 或者其他支持的模型
```

### 修改服务器配置

```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
```

### 数据库配置

默认使用 SQLite 数据库存储缓存。数据库文件会在运行目录下创建为 `analysis_result.db`。

## 🧪 测试

运行测试脚本验证功能：

```bash
python test_api.py octocat
```

## 📁 项目文件说明

```
github_analyzer/
├── __init__.py              # 包初始化，导出主要类和函数
├── analyzer.py              # 核心分析器，包含所有分析逻辑
├── ai_client.py             # AI 客户端，处理 OpenRouter API 调用
├── config.py                # 配置管理，从环境变量加载配置
├── flask_app.py             # Flask 应用，提供 REST API 接口
├── github_client.py         # GitHub API 客户端
├── github_queries.py        # GraphQL 查询定义
├── models.py                # 数据库模型定义
├── dev_pioneers.csv         # 开发者先驱数据，用于角色匹配
├── requirements.txt         # Python 依赖列表
├── .env.template           # 环境变量模板
├── run.py                  # 独立启动脚本
├── test_api.py             # API 测试脚本
├── setup.py                # 包安装配置
├── README.md               # 详细使用说明
├── DEPLOYMENT.md           # 部署指南
└── USAGE_GUIDE.md          # 本文件
```

## 🔄 与原始脚本的对比

### 原始 `scripts/analyze.py`

- 命令行工具
- 直接输出到控制台
- 配置文件依赖
- 单次分析

### 新的 `github_analyzer`

- ✅ Flask API 服务
- ✅ JSON 响应格式
- ✅ 环境变量配置
- ✅ 数据库缓存
- ✅ 错误处理
- ✅ 健康检查
- ✅ 完整文档
- ✅ 测试脚本
- ✅ 部署指南

## 🚨 注意事项

1. **API 限制**: GitHub API 有速率限制，每小时 5000 次请求
2. **首次分析**: 第一次分析用户可能需要 1-3 分钟
3. **缓存机制**: 分析结果会缓存，避免重复分析
4. **网络依赖**: 需要稳定的网络连接
5. **API 密钥**: 确保所有 API 密钥有效且有足够配额

## 🛠️ 故障排除

### 常见错误

1. **配置错误**
   ```
   ValueError: GITHUB_TOKEN environment variable is required
   ```
   解决：检查 `.env` 文件中的环境变量设置

2. **网络错误**
   ```
   Github request failed: 401 Unauthorized
   ```
   解决：检查 GitHub Token 是否有效

3. **用户不存在**
   ```
   Github user `username` doesn't exists.
   ```
   解决：确认用户名正确且用户存在

### 调试模式

启用调试模式获取更多日志信息：

```env
FLASK_DEBUG=True
```

## 📈 性能优化

1. **使用缓存**: 分析结果自动缓存到数据库
2. **并发处理**: 使用 asyncio 并发调用 API
3. **生产部署**: 使用 Gunicorn 等 WSGI 服务器

## 🔒 安全建议

1. 不要在代码中硬编码 API 密钥
2. 使用 HTTPS 部署到生产环境
3. 实施适当的速率限制
4. 定期轮换 API 密钥

## 📞 支持

如果遇到问题：

1. 查看日志输出
2. 运行测试脚本
3. 检查网络连接
4. 验证 API 密钥有效性

## 🎯 下一步

这个模块已经可以直接使用，你可以：

1. 集成到现有的 Flask 应用中
2. 作为微服务独立部署
3. 根据需要自定义分析逻辑
4. 添加更多的 API 端点
5. 实施更复杂的缓存策略

祝你使用愉快！🎉
