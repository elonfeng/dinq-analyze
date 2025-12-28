# Analyze 基准测试清单（sqlite / 可复用）

目标：用 **同一套脚本** 在本地（sqlite 隔离 DB）复现并量化 `dinq` 分析接口的：
- **job wall time**（从 `job.started` 到 `job.completed`）
- **每张卡耗时**（`card.completed.timing.duration_ms`）
- **资源卡细分耗时**（GitHub/LinkedIn/Scholar 资源抓取子步骤）
- **完整性**（业务卡 `internal=false` 的 `output.data` 不应为空；若不足则应给可展示 fallback，而不是 `{}`/`null`）

> 强烈建议用 sqlite 隔离 DB：如果直连共享 PG，容易出现“多实例抢跑 job_cards/事件不全”的测试失真。

---

## 1) 环境与运行方式

### 推荐（可重复的冷/热基准）

- 用 sqlite DB：`dinq/.local/local_test.db`（或脚本 `--fresh-db` 自动新建）
- 端口固定：`127.0.0.1:8091`
- 一键跑：`bash bench/run.sh`

### 两种模式

- **cold**：`force_refresh=true`（更接近“首次分析/强制重算”）
- **warm**：默认（更接近“缓存命中/重复查询”）
- **both**：先 cold 再 warm（对比缓存收益）

---

## 2) 样本集（建议最小集合）

每个 source 至少 2 个样本（轻/重），保证能看出“数据量放大”对资源抓取与 LLM 卡的影响。

### GitHub
- light：`nehanarkhede`
- heavy：`mdo`（PR、repo、活跃数据量更大）

### LinkedIn
- public profile URL（稳定可复现）：例如 `https://ca.linkedin.com/in/lindsay-scott-2ab8951`

### Scholar
- scholar id（可复现）：例如 `1zmDOdwAAAAJ`

> 你可以把公司常用用户样本加入 `bench/samples.json`，形成长期回归基准。

---

## 3) 指标采集（脚本会输出/落盘）

### Job 级
- `wall_time_db_s`：sqlite `job_events.created_at` 的 min/max 差值（推荐）
- `wall_time_client_s`：脚本侧计时（辅助）

### Card 级
- `duration_ms`：来自 SSE `card.completed.timing.duration_ms`
- `empty_business_data`：业务卡 `internal=false` 且 `output.data` 为空（需要关注）

### 资源卡细分（定位瓶颈）
- GitHub：`timing.github.*`（如 `pr_repos` 常是大头）
- LinkedIn：`timing.linkedin.raw_profile`
- Scholar：`kind=timing` 的 `stage/page_idx/cstart/fetch_ms/parse_ms`
  - 重点看 `fetch_profile`：即便并发，**最慢页**会决定下限

---

## 4) 检查项（Pass / Fail / Warning）

### 必须 Pass
- job 最终为 `completed` 或 `partial`（且 partial 有明确原因/可展示）
- 所有 **业务卡**（`internal=false`）`output.data` 不为空（或有可展示 fallback + reason）

### Warning（需要定位/优化）
- 任一资源卡（`resource.*`）`duration_ms > 30s`
- 任一 LLM 卡（如 `repos/role_model/summary/money/level`）`duration_ms > 15s`
- 出现重试：SSE 中 `card.progress step=retry`（要看是抓取问题、LLM 输出修复、还是质量门禁触发）

### Fail（需要修复）
- job 卡死（stream 不结束、卡长期 `running`）
- 业务卡静默 `{}` / `null`（无 retry、无 fallback、无诊断 artifact）

---

## 5) 如何解读“慢在哪里”

经验上常见主瓶颈：
- Scholar：`fetch_profile` 分页抓取慢（反爬/代理/网络），最慢页决定总耗时
- LinkedIn：`raw_profile` 抓取链路慢（第三方 actor/代理执行）
- GitHub：重度用户时 `repos/role_model/summary` 等 LLM 卡主导；资源卡里 `pr_repos` 可能最慢

---

## 6) 产物位置

脚本每次运行会生成：
- `.local/bench/output/<timestamp>/sse/<job_id>.sse`
- `.local/bench/output/<timestamp>/snapshot/<job_id>.json`
- `.local/bench/output/<timestamp>/report.json`
- `.local/bench/output/<timestamp>/report.md`
