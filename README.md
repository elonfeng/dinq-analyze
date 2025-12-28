# DINQ

DINQ 是分析服务（Python），统一通过 `/api/analyze` 生成卡片化分析结果，支持同步与 SSE 流式回放。系统面向多源数据（Scholar/GitHub/LinkedIn/Twitter/OpenReview/HuggingFace/YouTube），输出结构化卡片与可回放的事件流。

对外推荐链路（生产）：
- Frontend → Gateway：`/api/v1/analyze*`
- Gateway → 本服务（upstream）：`/api/analyze*`（并注入 `X-User-ID`）

## 快速开始
1) 安装依赖
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) 配置环境变量
- 参考：`docs/env_config.md`

3) 启动服务
```bash
python new_server.py
```

4) 健康检查
```bash
curl http://localhost:5001/health
```

## 文档入口
- 统一文档索引：`docs/README.md`
- 前端对接手册：`docs/frontend/README.md`
- OpenAPI：`docs/api/openapi.yaml`

## 核心能力
- 统一分析入口（`/api/analyze`），支持同步与 SSE 流式
- 任务管理与断线续传（`/api/analyze/jobs/<id>/stream`）
- 多源分析卡片（Scholar/GitHub/LinkedIn/Twitter/OpenReview/HuggingFace/YouTube）
- LLM Gateway 与卡片级调用（详见架构文档）

## 测试
- 测试指南：`TESTING.md`

## 兼容说明
分析相关旧 jobs 接口（如 `/api/jobs/*`、旧的 `card.data` 读取方式）已移除，统一使用 `/api/analyze*` 与 `output={data,stream}`。
其他历史业务接口请按需查阅：`docs/api/README.md` 与 `docs/legacy/README.md`。
