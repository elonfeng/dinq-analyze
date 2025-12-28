# DINQ 文档索引

本目录为项目统一文档入口，按“架构 / API / 前端 / 运维 / 业务功能”组织。历史文档不删除，但已在此做统一索引。

## 1) 快速开始
- 项目总览与启动：`README.md`
- 环境变量说明：`docs/env_config.md`
- 部署说明：`docs/production_deployment.md`
- 测试说明：`TESTING.md`

## 2) 架构与数据流
- 架构总览：`docs/architecture/overview.md`
- 模块职责：`docs/architecture/modules.md`
- 请求/数据流：`docs/architecture/dataflow.md`

## 3) API 文档
- OpenAPI 入口：`docs/api/openapi.yaml`
- API 索引：`docs/api/README.md`
- 统一入口（/api/analyze）：`docs/api/ANALYZE_API.md`
- 历史接口归档：`docs/legacy/README.md`

## 4) 前端对接
- 前端对接手册（统一入口/SSE/卡片渲染）：`docs/frontend/README.md`

## 5) 认证与日志
- 认证说明：`docs/authentication`
- Axiom 日志：`docs/axiom_logging.md`
- 系统级功能说明：`docs/system/README.md`

## 6) 其他专项说明
- Scholar 流程：`docs/scholar_processing_workflow.md`
- 数据模型：`docs/DATA_MODEL.md`
- 验证流程：`docs/verification`（目录）

---

如需新增文档：
- 新 API：优先补 `docs/api/openapi.yaml` + `docs/api/README.md`
- 新模块：补 `docs/architecture/modules.md`
- 新前端协议：补 `docs/frontend/README.md`
