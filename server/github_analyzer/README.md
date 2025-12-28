# GitHub Analyzer API

一个强大的 GitHub 用户分析工具，提供 Flask API 接口，可以深度分析 GitHub 用户的代码贡献、技能水平、项目影响力等。

## 功能特性

- 🔍 **深度用户分析**: 分析 GitHub 用户的代码贡献、技能标签、工作经验
- 🤖 **AI 驱动**: 使用 AI 生成用户标签、项目分析、角色模型匹配
- 📊 **数据可视化**: 提供详细的统计数据和活动分析
- 💰 **薪资评估**: 基于 Google 标准的技能水平和薪资评估
- 🎯 **角色匹配**: 与知名开发者进行相似度匹配
- 💾 **智能缓存**: 数据库缓存避免重复分析
- 🌐 **RESTful API**: 标准的 HTTP API 接口

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制环境变量模板：
```bash
cp .env.template .env
```

编辑 `.env` 文件，填入你的 API 密钥：

```env
# GitHub API Token (必需)
GITHUB_TOKEN=your_github_token_here

# OpenRouter API Key (必需)  
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Crawlbase Token (必需)
CRAWLBASE_TOKEN=your_crawlbase_token_here

# 可选配置
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
```

### 3. 获取 API 密钥

#### GitHub Token
1. 访问 [GitHub Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. 点击 "Generate new token"
3. 选择权限: `public_repo`, `read:user`
4. 复制生成的 token

#### OpenRouter API Key
1. 访问 [OpenRouter](https://openrouter.ai/keys)
2. 注册账号并获取 API Key
3. 复制 API Key

#### Crawlbase Token
1. 访问 [Crawlbase](https://crawlbase.com/)
2. 注册账号并获取 Token
3. 复制 Token

### 4. 启动服务

```bash
python run.py
```

服务将在 `http://localhost:5000` 启动。

## API 使用

### 分析 GitHub 用户 (POST)

```bash
curl -X POST \
  http://localhost:5000/api/github/analyze \
  -H "Content-Type: application/json" \
  -d '{"username": "octocat"}'
```

### 分析 GitHub 用户 (GET)

```bash
curl "http://localhost:5000/api/github/analyze?username=octocat"
```

### 健康检查

```bash
curl http://localhost:5000/api/health
```

### API 帮助

```bash
curl http://localhost:5000/api/github/analyze/help
```

## 响应格式

成功响应示例：

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
    "valuation_and_level": {
      "level": "L5",
      "salary_range": "$150,000 - $220,000",
      "total_compensation": "$200,000 - $350,000"
    },
    "role_model": {
      "name": "Linus Torvalds",
      "similarity_score": 0.85,
      "reason": "Similar open source leadership and system-level contributions"
    },
    "roast": "With 8000 stars and a bio about being a cat, octocat is clearly the most famous feline in tech!"
  }
}
```

错误响应示例：

```json
{
  "error": "User not found",
  "message": "GitHub user \"nonexistentuser\" does not exist or is not accessible"
}
```

## 集成到 Flask 项目

### 方法 1: 直接导入

```python
from github_analyzer import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
```

### 方法 2: 蓝图集成

```python
from flask import Flask
from github_analyzer.flask_app import create_app

# 创建主应用
main_app = Flask(__name__)

# 创建分析器应用
analyzer_app = create_app()

# 注册蓝图或挂载子应用
# 这里需要根据你的具体需求调整
```

### 方法 3: 作为微服务

将此服务作为独立的微服务运行，通过 HTTP 请求调用。

## 项目结构

```
github_analyzer/
├── __init__.py              # 包初始化
├── analyzer.py              # 核心分析器
├── ai_client.py             # AI 客户端
├── config.py                # 配置管理
├── flask_app.py             # Flask 应用
├── github_client.py         # GitHub API 客户端
├── github_queries.py        # GraphQL 查询
├── models.py                # 数据库模型
├── dev_pioneers.csv         # 开发者先驱数据
├── requirements.txt         # 依赖列表
├── .env.template           # 环境变量模板
├── run.py                  # 启动脚本
└── README.md               # 使用说明
```

## 注意事项

1. **API 限制**: GitHub API 有速率限制，建议合理使用
2. **缓存机制**: 分析结果会缓存到 SQLite 数据库，避免重复分析
3. **网络依赖**: 需要稳定的网络连接访问各种 API
4. **资源消耗**: AI 分析可能需要一些时间，请耐心等待

## 故障排除

### 常见错误

1. **配置错误**: 检查环境变量是否正确设置
2. **网络错误**: 检查网络连接和 API 密钥有效性
3. **用户不存在**: 确认 GitHub 用户名正确且公开可访问

### 日志查看

应用会输出详细的日志信息，帮助诊断问题。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
