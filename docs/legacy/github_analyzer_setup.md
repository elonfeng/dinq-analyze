# GitHub分析器集成配置指南

## 📋 概述

GitHub分析器已成功集成到DINQ项目中，提供深度的GitHub用户分析功能。本文档将指导您完成必要的配置步骤。

## 🔑 必需的API密钥

GitHub分析器需要以下三个API密钥才能正常工作：

### 1. GitHub Token (GITHUB_TOKEN)

**用途**: 访问GitHub API获取用户数据、仓库信息、Pull Request等

**获取方式**:
1. 访问 [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. 点击 "Generate new token (classic)"
3. 设置token名称，如 "DINQ GitHub Analyzer"
4. 选择以下权限:
   - `public_repo` - 访问公共仓库
   - `read:user` - 读取用户信息
   - `read:org` - 读取组织信息（可选）
5. 点击 "Generate token"
6. 复制生成的token（只显示一次）

**示例**: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 2. OpenRouter API Key (OPENROUTER_API_KEY)

**用途**: 使用AI模型进行用户分析、标签生成、角色匹配等

**获取方式**:
1. 访问 [OpenRouter](https://openrouter.ai/)
2. 注册账户并登录
3. 前往 [API Keys页面](https://openrouter.ai/keys)
4. 点击 "Create Key"
5. 设置key名称，如 "DINQ GitHub Analyzer"
6. 复制生成的API key

**示例**: `sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**推荐模型**: `anthropic/claude-3.5-sonnet` (默认)

### 3. Crawlbase Token (CRAWLBASE_TOKEN)

**用途**: 网页抓取功能，获取GitHub页面的额外信息（如Used By、Contributors等）

**获取方式**:
1. 访问 [Crawlbase](https://crawlbase.com/)
2. 注册账户并登录
3. 前往Dashboard
4. 复制 "Normal Token" 或 "JavaScript Token"

**示例**: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## ⚙️ 配置方法

### 方法1: 环境变量配置（推荐）

在项目根目录的 `.env` 文件中添加：

```env
# GitHub分析器配置
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CRAWLBASE_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 可选配置
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

### 方法2: API密钥文件配置

在 `server/config/api_keys.py` 文件中添加：

```python
API_KEYS = {
    # 现有的API密钥...
    
    # GitHub分析器密钥
    'GITHUB_TOKEN': 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    'OPENROUTER_API_KEY': 'sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    'CRAWLBASE_TOKEN': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
}
```

## 🚀 API端点

GitHub分析器集成后提供以下API端点：

### 分析GitHub用户

**POST** `/api/github/analyze`
```bash
curl -X POST "http://localhost:5001/api/github/analyze" \
  -H "Content-Type: application/json" \
  -H "Userid: your_user_id" \
  -d '{"username": "octocat"}'
```

**GET** `/api/github/analyze?username=octocat`
```bash
curl -H "Userid: your_user_id" \
  "http://localhost:5001/api/github/analyze?username=octocat"
```

### 其他端点

- `GET /api/github/health` - 健康检查
- `GET /api/github/help` - API使用说明
- `GET /api/github/stats` - 用户使用统计

## 📊 功能特性

### 🔍 深度用户分析
- 代码贡献统计（additions/deletions）
- 编程语言分布
- 工作经验计算
- 活动模式分析

### 🤖 AI驱动分析
- 用户技能标签生成
- 项目标签分析
- 最有价值PR识别
- 角色模型匹配

### 💰 薪资评估
- 基于Google标准的级别评估
- 薪资范围估算
- 技能水平分析

### 🎯 角色匹配
- 与知名开发者相似度匹配
- 基于编程语言和贡献模式
- 提供匹配原因说明

### 💾 智能缓存
- SQLite数据库缓存
- 避免重复分析
- 提高响应速度

## 🔒 使用限制

- **月度限制**: 每用户每月10次分析
- **时间窗口**: 30天滚动窗口
- **已激活用户**: 不受使用限制
- **认证要求**: 需要verified用户权限

## 🧪 测试

运行集成测试验证配置：

```bash
cd tests/integration_tests
python test_github_analyzer.py
```

测试将验证：
- API端点可访问性
- 配置正确性
- 分析功能完整性
- 错误处理机制

## 📝 响应示例

```json
{
  "success": true,
  "username": "octocat",
  "data": {
    "user": {
      "name": "The Octocat",
      "company": "@github",
      "location": "San Francisco",
      "tags": ["open source", "git", "collaboration"]
    },
    "overview": {
      "work_experience": 15,
      "stars": 8000,
      "repositories": 8,
      "pull_requests": 291,
      "additions": 1000000,
      "deletions": 500000
    },
    "valuation_and_level": {
      "level": "L6",
      "salary_range": "$200,000 - $300,000",
      "total_compensation": "$300,000 - $500,000"
    },
    "role_model": {
      "name": "Linus Torvalds",
      "similarity_score": 0.85,
      "reason": "Similar open source leadership"
    },
    "roast": "With 8000 stars and a bio about being a cat, octocat is clearly the most famous feline in tech!"
  },
  "usage_info": {
    "remaining_uses": 9,
    "reset_date": "2025-06-25"
  }
}
```

## ⚠️ 注意事项

1. **API限制**: GitHub API有速率限制，请合理使用
2. **分析时间**: 完整分析可能需要30-120秒
3. **网络依赖**: 需要稳定的网络连接
4. **成本考虑**: OpenRouter和Crawlbase为付费服务
5. **隐私保护**: 只分析公开的GitHub信息

## 🔧 故障排除

### 常见错误

**配置错误**:
```
ValueError: Missing required environment variables: GITHUB_TOKEN
```
**解决方案**: 检查API密钥配置

**GitHub API限制**:
```
GitHub API rate limit exceeded
```
**解决方案**: 等待限制重置或使用更高级别的token

**OpenRouter错误**:
```
OpenRouter API error: insufficient credits
```
**解决方案**: 检查OpenRouter账户余额

**Crawlbase错误**:
```
Crawlbase API error: invalid token
```
**解决方案**: 验证Crawlbase token有效性

### 日志查看

GitHub分析器的日志会包含trace ID，便于调试：

```bash
tail -f logs/dinq_allin_one.log | grep github_analyzer
```

## 📞 支持

如果遇到问题，请：

1. 检查API密钥配置
2. 运行测试脚本验证
3. 查看日志文件
4. 检查网络连接
5. 验证API服务状态

---

**配置完成后，GitHub分析器将为DINQ项目提供强大的GitHub用户分析能力！** 🎉
