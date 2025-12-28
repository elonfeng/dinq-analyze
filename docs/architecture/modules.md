# 模块职责

## server/analyze
- **统一入口**：`/api/analyze` 处理 sync/stream
- **规则与卡片计划**：`server/analyze/rules.py`
- **Pipeline Executor**：执行 full_report + 依赖卡片

## server/tasks
- **JobStore**：job/cad 生命周期
- **EventStore**：SSE 事件持久化与回放
- **ArtifactStore**：full_report 等产物存储
- **Scheduler**：并行执行 ready cards（可在 API 进程内运行，也可在独立 runner 进程运行；由 `DINQ_EXECUTOR_MODE` 控制）

## server/llm
- **Gateway**：统一 OpenRouter、JSON 修复、缓存
- **LLM Cache**：持久化 LLM 结果

## server/services
- **Scholar**：搜索/抓取/分析/缓存/角色模型/评分
- **GitHub / LinkedIn / Twitter / HF / OpenReview / YouTube**：各自分析器

## server/api
- 业务 API 路由（job board、verification、auth 等）
- 旧接口兼容（scholar sync / pk / legacy stream）

## src/utils & src/models
- ORM 模型、通用 DB 工具
- 业务仓库与缓存封装
