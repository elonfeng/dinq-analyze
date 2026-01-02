# 架构总览

当前项目为单体服务（Flask + SQLite/Postgres），核心能力是“统一分析入口 + 卡片化输出 + 流式回放”。

## 关键目标
- 统一入口：`/api/analyze` 统一承载 Scholar / GitHub / LinkedIn 等分析
- 卡片化输出：每个功能输出为 card，可独立执行/重试/缓存
- 流式回放：SSE 持久化事件流，前端断线可继续拉取
- 单体部署：不依赖额外的外部缓存服务

## 核心组件
- **API 网关层**：`server/analyze/api.py` + 旧接口兼容（如 `/api/stream`、`/api/scholar-pk`）
- **任务系统**：`server/tasks/*`（JobStore / EventStore / ArtifactStore / Scheduler）
- **规则驱动 Pipeline**：`server/analyze/*`（卡片顺序、依赖、执行）
- **LLM Gateway**：`server/llm/*`（OpenRouter 路由、缓存、JSON 修复、流式 delta）
- **业务分析器**：`server/services/*`（Scholar / GitHub / LinkedIn 等）

## 执行模式
- **同步模式**：/api/analyze `mode=sync`
- **异步模式**：/api/analyze `mode=async`（默认，只创建 job）
- **流式回放**：/api/analyze/jobs/<id>/stream（SSE，支持断线续传）
- **执行拓扑**：单机本地优先（API 进程内启动 scheduler 执行 cards）

## 存储
- **Job + Event + Artifact**：数据库表
- **LLM Cache**：数据库表
- **业务缓存**：Scholar 等模块使用 DB 缓存

## 增量输出形态
- **结构化列表增量**：`card.append`（papers/repo previews 边抓边出；快照可恢复）
- **文本流式增量**：`card.delta`（Markdown/text 卡片分段输出；为控写入会按 chunk flush）

## 兼容旧接口
- `/api/stream`：旧 Scholar SSE
- `/api/scholar-pk`：PK 流式接口
- 各 analyzer 专用路由仍保留
