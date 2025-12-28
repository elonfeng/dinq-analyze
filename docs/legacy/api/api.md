说明：本文档为历史流式协议说明，新协议以 `docs/frontend/README.md` 为准（card.* 事件）。

一、统一事件结构（所有流式接口通用）

  每一帧都是一行：

  - 文本：data: {json}\n\n
  - JSON 大致是：

    {
      "source": "scholar|github|linkedin",
      "event_type": "start|progress|data|final|error|end|ping",
      "step": "逻辑步骤名（可选）",
      "message": "人类可读文案",
      "progress": 0,
      "payload": { "结构化数据（可选）" },
      "type": "legacy 类型（可选，兼容旧前端）",
      "content": "legacy 内容（可选，有些事件会有）"
    }

  前端主要用：event_type、step、message、progress、payload、type。

  ———

  二、整体阶段时间线

  1）启动阶段（event_type = "start"）

  - 每次调用一开始都会有一条：
      - source: 对应服务（scholar / github / linkedin）
      - event_type: "start"
      - message: 类似：
          - Scholar："Starting Scholar analysis: <query>"
          - GitHub："Starting GitHub user analysis: <username>"
          - LinkedIn："Starting LinkedIn analysis for <name or URL>"
      - payload：起始参数，例如：
          - Scholar：{"query": "..."}
          - PK：{"researcher1": "...", "researcher2": "..." }
          - GitHub：{"username": "octocat"}
  - 作用：你可以拿来初始化 UI（显示“开始分析…”）。

  ———

  2）配额 & 缓存阶段（event_type = "progress"，早期几条）

  统一由 build_stream_task_fn 发出：

  - usage_check：检查用量限制
      - event_type: "progress"
      - step: "usage_check"
      - message: "Checking usage limits..."
      - 如果配额超了，后面会直接出一条 error + 结束。
  - check_cache：查缓存
      - step: "check_cache"
      - message: "Checking cache..."
  - cache_found（有缓存命中时才会有）
      - step: "cache_found"
      - message: "Found cached result"
      - 随后很快就会返回一条 final 事件，payload 里通常会带：
          - from_cache: true
          - usage_info: {remaining_uses, total_usage, ...}
  - 对前端意义：
      - 可以显示“命中缓存”“正在检查配额”等辅助文案；
      - 如果你只关心最终结果，可以忽略这些，只要在 final 里看 from_cache。

  ———

  3）核心分析阶段（大量 progress 事件）

  这个阶段是每个服务自己的逻辑，但统一形式是：

  - event_type: "progress"
  - step: 具体阶段标签
  - message: 用户可读的文案
  - progress: 0–100（不一定是严格线性）

  常见的：

  - Scholar /api/stream
      - 由 create_state_message 生成，多数 step 会是 "thinking" 或 "completed"，但 message 里写清具体动作：
          - "Analyzing researcher: <query>"
          - "Preparing to retrieve scholar data..."
          - "Academic data retrieval complete ✓"
          - "Scholar report generated"（进度接近 95）
      - 还有一条 legacy status：
          - type: "status"
          - event_type: "progress"
          - message 类似 "Processing query request..."
  - Scholar PK /api/scholar-pk
      - 类似 Scholar，但会带上 researcher1 / 2 的前缀，比如：
          - "Researcher 1: 获取缓存..."，"Researcher 2: Starting retrieval..." 等
      - 进度会在 5–85 之间映射两个人的抓取进度，然后 88 之后是 PK 计算和报告生成。
  - GitHub /api/github/analyze-stream
      - 文档里列出典型 step：
          - usage_check、init_analyzer、check_cache、cache_found
          - profile_fetch、repos_fetch、activity_analysis、valuation 等
      - 你可以据 step 做更细粒度的 UI（比如显示“正在拉取仓库信息…”）。
  - LinkedIn /api/linkedin/analyze / /compare
      - 统一通过 ctx.progress(step, message, payload=...) 发：
          - 早期会有 cache_lookup
          - 后面是分析内部的步骤（抓档案、AI 分析各维度等），但 step 命名主要在 analyzer 内部，不强依赖某个固定列表。
      - 前端主要根据 message + progress 更新状态即可。

  ———

  4）关键业务数据事件（event_type = "data"）

  这是前端最重要的“内容阶段”，不同接口有不同的 type / payload：

  - Scholar 单人 /api/stream
      - 来自 create_report_data_message：
          - event_type: "data"
          - type: "reportData"（legacy）
          - payload 和 content 相同，包含：
              - jsonUrl: 报告 JSON 地址
              - htmlUrl: 报告 HTML 地址
              - researcherName
              - scholarId（可选）
              - completeness: 完整度信息（可选）
      - 通常这条一来，你就可以把“报告链接 / scholarId”抽出来驱动后续 UI。
  - Scholar PK /api/scholar-pk
      - pkData：PK 结果本身
          - event_type: "data"
          - type: "pkData"
          - payload/content: 对比结果（打分、多维度比较等）
      - reportData：PK 报告链接
          - event_type: "data"
          - type: "reportData"
          - payload/content：
              - jsonUrl
              - researcher1Name
              - researcher2Name
              - scholarId1 / scholarId2（可选）
  - GitHub /api/github/analyze-stream
      - 目前主要是一个 final 事件承载全部数据（见下一节）；中途没有类似 reportData 的 data 事件是必须的。
      - 如果有中间 data 事件，也是统一 schema，payload 里可能放分阶段结果（例如某一块分析完成），但前端最稳妥是等 event_type="final"。
  - LinkedIn /api/linkedin/analyze 与 /compare
      - 同样主要使用 final 携带整体结果；
      - progress 阶段 payload 里，偶尔会放分部结果或当前阶段的结构化信息（具体取决于 analyzer 的实现），但协议上没有固定 type="reportData" 这种强约定。

  ———

  5）最终结果 & 收尾（final / error / end）

  - 成功完成：event_type = "final"
      - 由各接口的 result_event_builder 统一构造：
          - Scholar /api/stream：
              - payload ≈ {"jsonUrl", "htmlUrl", "researcherName", "scholarId", ...}（即前面 work 返回的 report_data）
              - 实际上你早在 type="reportData" 的 data 事件里就拿到了这些；final 更像“确认结束 + 合并结果”。
          - Scholar PK /api/scholar-pk：
              - payload: {"ok": true}，PK 的详细内容在前面的 pkData / reportData 里。
          - GitHub analyze / compare：
              - payload（或 payload.data）是完整分析结果：
                  - user、overview、activity、top_projects、valuation_and_level、role_model、roast 等。
          - LinkedIn analyze：
              - payload.data: LinkedIn 分析结果（包含 profile_data + 各种 AI 分析字段）。
          - LinkedIn compare：
              - payload.data: PK 结果（多维度对比 + roast 等），report_urls 里可能有报告链接。
  - 出错：event_type = "error"
      - 所有服务统一用 create_error_event：
          - payload：

            {
              "code": "internal_error|usage_limit|cancelled|timeout|...",
              "message": "错误描述",
              "retryable": true/false,
              "detail": { ... 可选上下文 ... }
            }
          - 同时为了兼容旧前端，还会有：
              - content: 错误文案
              - error: 错误文案
      - 前端应该：
          - 在 event_type === "error" 时，从 payload.message 展示错误；
          - 根据 payload.retryable 判断是否提示“可重试”。
  - 流关闭：event_type = "end"
      - 一定会发：
          - 正常结束："Analysis stream closed"
          - 超时："Analysis stream closed (timeout)"（前面还会有一条 timeout 的 error）
      - 前端可以在收到 end 后清理 SSE reader，把 UI 状态标记为“已结束”。
  - 心跳：event_type = "ping"（可选）
      - 当长时间没有进展时，runner 会每隔 keepalive_seconds 发一条：
          - step: "keepalive"
          - type: "ping"
      - 前端可以忽略或用来做“连接状态”提示。

  ———

  三、前端实践总结：怎么按阶段消费

  最简单、稳定的写法是：

  - start：初始化 UI；
  - progress：
      - 用 progress 数值画进度条；
      - 用 step / message 显示当前阶段说明；
  - data：
      - 看 type 决定业务逻辑：
          - Scholar：reportData / pkData
          - Scholar PK：pkData + reportData
      - 解析 payload / content 把关键字段拿出来；
  - final：
      - 当作“整体完成信号 + 兜底结果”，对 GitHub / LinkedIn 来说是主结果；
  - error：
      - 从 payload 里拿错误信息，展示给用户；
  - end：
      - 关闭流、收尾 UI。
