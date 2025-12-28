# 请求/数据流

## 统一入口：/api/analyze（流式）
1. 前端提交 `source + input + cards + options`
2. 生成 job & card plan
3. 执行卡片（取决于执行拓扑）：
   - `DINQ_EXECUTOR_MODE=inprocess`：API 进程内 scheduler 执行
   - `DINQ_EXECUTOR_MODE=external`：独立 runner 从 DB claim cards 执行（生产推荐）
4. 对 `scholar/github/linkedin`：先执行内部 `resource.*` 形成依赖拆分；对其他 source 仍以 `full_report` 为主
5. 每个卡片输出：
   - `card.progress`：阶段进度（可选）
   - `card.append`：结构化列表增量（可选，preview 边抓边出）
   - `card.delta`：LLM 分段输出（可选；为控写入会按 chunk flush）
   - `card.completed`：完整 payload
6. EventStore 持久化事件流，前端通过 SSE 回放

## 统一入口：/api/analyze（同步）
1. 直接串行执行 full_report + 其他卡片
2. 返回汇总 cards
3. 仍会写入 job/card 状态

## 事件类型（SSE）
- `job.started`
- `card.started`
- `card.progress`
- `card.append`
- `card.delta`（payload: {card, field, section, delta}）
- `card.completed`（payload: {card, payload}）
- `card.failed`
- `job.completed` / `job.failed`
- `ping`（keepalive）

## 断线续传
- `/api/analyze/jobs/<id>/stream?after=<seq>`
- 通过 seq 保证幂等回放

## Scholar 分析主流程
search -> fetch_profile -> analyze -> enrich -> persist -> render

## 缓存策略
- Scholar 缓存：DB 表
- LLM 缓存：DB 表
- 任务事件：DB 表
