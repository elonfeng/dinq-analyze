# DINQ API 文档索引

本目录提供 API 协议的统一入口与历史接口索引。**新增接口请先更新 `docs/api/openapi.yaml`。**

## 1) 统一入口（推荐）
- OpenAPI：`docs/api/openapi.yaml`
- 统一分析入口：`docs/api/ANALYZE_API.md`

## 2) 基础信息
- **Base URL**
  - 开发环境（Gateway）：`http://localhost`
  - 测试环境（Gateway）：`https://test-api.dinq.ai`（如仍在使用）
  - 生产环境（Gateway）：`https://api.dinq.me`（当前部署）
  - 旧域名（如仍在使用）：`https://api.dinq.ai`
- **认证方式**
  - `Authorization: Bearer <gateway_jwt>`

## 3) 核心接口（新架构）
- `POST /api/v1/analyze`（支持 `mode=async|sync`）
- `GET /api/v1/analyze/jobs/{job_id}`
- `GET /api/v1/analyze/jobs/{job_id}/stream?after=<seq>`
- `GET /health`

> 说明：`docs/api/openapi.yaml` 主要覆盖分析服务（上游）与历史接口（`/api/analyze*`、`/api/stream*` 等）。
> 前端对接 Gateway 三接口请优先看：`docs/frontend/README.md`。
> 需要卡片字段/示例（scholar/github/linkedin）请看：`docs/frontend/ANALYZE_CARDS.md`。

## 4) 旧接口（兼容）
以下接口仍保留，但不建议新业务继续接入：
- `POST /api/stream`（旧 Scholar SSE）
- `POST /api/scholar-pk`（学者 PK）
- `GET|POST /api/github/analyze`
- `POST /api/github/analyze-stream`
- 其他历史接口详见：`docs/api/openapi.yaml`

## 5) 相关业务文档（历史保留）
- Scholar Query：`docs/legacy/api/scholar_query.md`
- Scholar PK：`docs/legacy/api/scholar_pk.md`
- Scholar Name Lookup：`docs/legacy/api/scholar_name_lookup.md`
- Top Talents：`docs/legacy/api/top_talents.md`

## 6) 错误处理（统一建议）
```json
{
  "success": false,
  "error": "error_message",
  "details": {}
}
```

## 6.1) 运维调试（DB 快速排查 analyze job）
- 查看某个 job 的 cards/output/events（需要 `psql` + DB URL 环境变量）：
  - `scripts/db/inspect_analyze_job.sh <job_id> [subject_key]`

## 7) 变更规则
- 新接口：先补 OpenAPI，再补示例
- 旧接口：仅维护兼容性，不新增特性
