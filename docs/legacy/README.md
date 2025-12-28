# Legacy 文档归档

本目录用于统一归集历史/过时文档，避免与新架构文档混淆。新文档请从 `docs/README.md` 进入。

## 目录结构
- `docs/legacy/api/`：历史 API/协议说明（旧接口、旧 SSE 协议）
- `docs/legacy/`：历史功能文档或单点说明

## 主要归档内容
- 旧 API 说明与示例：`docs/legacy/api/`
- 旧前端流式协议：`docs/legacy/frontend_streaming_integration.md`
- 旧 GitHub 分析与流式接口：`docs/legacy/github_analyzer_api.md`、`docs/legacy/github_analyzer_streaming_api.md`
- 旧学者 PK：`docs/legacy/scholar_pk_api.md`
- 旧 Job Board 文档：`docs/legacy/job_board_api.md`、`docs/legacy/job_board_interactions.md`
- 旧上传/人才迁移说明：`docs/legacy/IMAGE_UPLOAD_API.md`、`docs/legacy/TALENT_MOVE_API.md`

## 使用原则
- 新需求：请使用 `docs/api/openapi.yaml` 与 `docs/frontend/README.md`
- 旧系统兼容：仅在维护历史功能时参考此目录
