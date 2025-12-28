# GitHub 分析器集成配置指南（已脱敏）

本文档用于说明 DINQ 的 GitHub 分析能力如何配置与验证。

重要说明：
- 本文档 **不包含任何真实密钥**（历史上曾出现过真实 token，已移除）
- 请通过环境变量或本地 `.env.local` 注入密钥，**不要把密钥提交到仓库**

## 必需环境变量

### 1) `GITHUB_TOKEN`

用途：访问 GitHub API 获取用户/仓库/PR 等数据。

建议权限（classic PAT 示例）：
- `public_repo`
- `read:user`
- `read:org`（可选）

示例（占位符）：

```env
GITHUB_TOKEN=ghp_<YOUR_TOKEN>
```

### 2) `OPENROUTER_API_KEY`

用途：调用 OpenRouter 模型做 LLM 分析。

示例（占位符）：

```env
OPENROUTER_API_KEY=sk-or-v1-<YOUR_KEY>
```

### 3) Crawlbase（`CRAWLBASE_API_TOKEN` / `CRAWLBASE_TOKEN`）

用途：抓取 GitHub 页面补全信息（如 used-by / contributors 等）。

示例（占位符）：

```env
CRAWLBASE_API_TOKEN=<YOUR_TOKEN>
```

## 配置方式（推荐）

把密钥放到以下任意位置之一：
- 本地开发：`.env.local`（已在 `.gitignore` 中）
- CI/生产：系统环境变量（推荐）

## API 端点（示例）

分析 GitHub 用户：

```bash
curl -X POST "http://localhost:5001/api/github/analyze" \
  -H "Content-Type: application/json" \
  -H "Userid: your_user_id" \
  -d '{"username": "octocat"}'
```

健康检查：

```bash
curl -sS "http://localhost:5001/api/github/health"
```

## 排障要点

- 401/403：检查 `GITHUB_TOKEN` 是否有效、权限是否足够
- LLM 失败：检查 `OPENROUTER_API_KEY`、模型名、以及网络连通性
- 抓取失败：检查 Crawlbase token 与相关开关
