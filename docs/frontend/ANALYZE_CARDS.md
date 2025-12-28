# Analyze 卡片协议（前端对接详版）

本文档补齐「前端怎么接 / 返回哪些卡片 / 字段格式是什么」的细节说明。

> 重要：前端请只调用 **Gateway**（`https://api.dinq.me`）对外 3 个接口；不要直连分析服务上游（`74.48.107.93:8080`）。

---

## 0) 对接总览（推荐流程）

1. 前端拿到 `Authorization: Bearer <jwt>`（登录态）
2. `POST /api/v1/analyze` 创建任务（推荐 `mode=async`）
3. 解析 SSE 事件并渲染卡片：
   - `card.prefill`：缓存预填充（可选；用于“先展示旧结果再后台刷新”）
   - `card.append`：结构化列表增量（可选；papers/repo previews 边抓边出）
   - `card.delta`：流式增量（可选）
   - `card.completed`：最终卡片数据（用于落盘/覆盖）
4. 收到 `job.completed/job.failed` 后主动 `abort()` 连接
5. 断线续传：用 `job_id` + 最后 `seq` 调 `GET /api/v1/analyze/jobs/<job_id>/stream?after=<seq>`
6. 需要“最终一致”可再拉一次快照：`GET /api/v1/analyze/jobs/<job_id>`
7. 依赖与执行顺序（DAG）：见 `docs/frontend/ANALYZE_DAG.md`

---

## 1) 通用协议（3 个接口）

### 1.0 哪些卡支持 stream_spec（前端零硬编码分段渲染）

目前只有“天然适合流式展示的文本/Markdown 卡”会启用 `stream_spec`（JSON 对象类卡片不做流式，避免“半截 JSON”导致 UX 很差）。

| source | card | stream_spec.field | stream_spec.format | stream_spec.sections |
|---|---|---|---|---|
| `scholar` | `summary` | `critical_evaluation` | `markdown` | `overview/strengths/risks/questions` |
| `github` | `roast` | `roast` | `markdown` | `main` |
| `linkedin` | `roast` | `roast` | `markdown` | `main` |
| `linkedin` | `summary` | `about` | `markdown` | `main` |

> 说明：
> - 真实渲染时请以快照的 `cards.<card>.stream_spec`（或 SSE 的 `card.started.payload.stream`）为准，表格仅是“当前实现”的说明。
> - `card.delta` 会携带 `field/section/format`，前端**不需要**解析服务端内部的分段 marker。

### 1.1 POST /api/v1/analyze（create job）

请求体：

```json
{
  "source": "scholar|github|linkedin|twitter|openreview|huggingface|youtube",
  "mode": "async|sync",
  "input": {},
  "cards": ["profile", "summary"],
  "options": {}
}
```

- `cards`：可不传 / 传空数组 `[]` → 使用该 `source` 的默认卡片集合（通常更慢、更贵）
- `cards` 传子集时：后端会**自动补齐依赖**（对 `scholar/github/linkedin` 可能出现内部 `resource.*` 依赖；对其他 source 仍主要依赖 `full_report`）
- `options`：可选（建议前端“当成策略开关”，不要强依赖其细节）
  - `freeform=true`：模糊输入→候选实体确认（不创建 job）
  - `force_refresh=true`：跳过缓存读取/预填充，强制重算（但仍会写入/更新缓存）

Header：
- `Authorization: Bearer <gateway_jwt>`
- 可选：`Idempotency-Key: <string>`（同一请求重试不产生重复 job）

### 1.2 GET /api/v1/analyze/jobs/<job_id>（job status）

返回结构（快照）：

```json
{
  "success": true,
  "job": {
    "job_id": "....",
    "source": "scholar",
    "status": "queued|running|completed|partial|failed",
    "created_at": "2025-12-20T09:00:00",
    "updated_at": "2025-12-20T09:00:30",
    "last_seq": 12,
    "next_after": 12,
    "cards": {
      "profile": { "status": "completed", "internal": false, "output": { "data": {}, "stream": {} } },
      "summary": {
        "status": "running",
        "internal": false,
        "stream_spec": { "field": "critical_evaluation", "format": "markdown", "sections": ["overview", "strengths", "risks", "questions"] },
        "output": { "data": null, "stream": {} }
      }
    }
  }
}
```

补充：
- `cards.<card>.internal=true`：内部卡片（`resource.*`、`full_report`），前端一般不渲染。
- `cards.<card>.stream_spec`：用于零硬编码渲染流式增量（field/format/sections）；若不存在表示该卡不启用流式/分段协议。

卡片状态（`cards.<card>.status`）常见值：
- `pending`：等待依赖（通常等 `full_report`）
- `ready`：可执行（等待调度器领取）
- `running`：执行中
- `completed`：完成
- `failed`：失败
- `skipped`：被跳过（例如 `full_report` 失败后，后续卡片会被跳过避免任务卡死）

### 1.3 GET /api/v1/analyze/jobs/<job_id>/stream?after=<seq>（SSE stream）

SSE frame 是标准 `data: <json>\n\n`。

统一事件结构：

```json
{
  "source": "analysis",
  "event_type": "job.started|card.started|card.prefill|card.progress|card.delta|card.completed|card.failed|job.completed|job.failed|ping",
  "message": "",
  "payload": {}
}
```

关键点：
- `payload.job_id`：任务 ID（`job.started` 的 payload 内会出现）
- `payload.seq`：递增序号（用于断线续传 after=seq）
- `ping`：keepalive 心跳（可忽略）
- 服务端在发出 `job.completed/job.failed` 后会自动关闭连接（前端也可以主动 abort）
- `card.delta` 为控成本/控写入会按 chunk 批量 flush；若需要“打字机”效果，建议前端对 delta 内容自行做逐字动画。

典型事件 payload：
- `job.started`：`{ job_id, source, seq }`
- `card.started`：`{ job_id, seq, card, status:"running", internal?:boolean, stream?:{ field, format, sections: string[] } }`
- `card.prefill`：`{ job_id, seq, card, payload:{ data, stream }, cache:{ hit:true, stale:true, as_of:"...", fingerprint?:string } }`
- `card.progress`：`{ job_id, seq, card, step:"...", message:"...", data?:{...} }`（`card` 可能是内部 `resource.*`）
- `card.append`：`{ job_id, seq, card, path, items, dedup_key, cursor?, partial? }`
- `card.delta`：`{ job_id, seq, card, field, section, format, delta }`
- `card.completed`：`{ job_id, seq, card, payload:{ data, stream }, internal?:boolean }`
- `card.failed`：`{ job_id, seq, card, internal?:boolean, error:{ code, message, retryable } }`
- `job.completed`：`{ job_id, seq, status:"completed|partial" }`
- `job.failed`：`{ job_id, seq, status:"failed" }`

---

## 2) scholar（学者分析）

### 2.1 input 怎么填

推荐（统一写法，稳定）：

```json
{ "content": "Y-ql3zMAAAAJ" }
```

`content` 支持：
- Scholar ID（推荐）
- Scholar 主页 URL（`https://scholar.google.com/citations?user=...`）
- 人名/模糊输入（会尝试搜索解析；命中不保证 100%）

说明：
- 抓取与缓存策略（是否启用 Crawlbase、cache age 等）由服务端环境变量控制，前端不需要传入，也不应依赖这些“调参”字段。

### 2.2 默认 cards

`profile / metrics / papers / citations / coauthors / role_model / news / level / summary`

> 注：对 `scholar/github/linkedin` 会出现内部 `resource.*` 卡片用于抓取/拆依赖/缓存；`full_report` 是内部聚合卡片，前端一般忽略它即可（SSE 的 `card.*` 事件会标 `internal=true`）。

### 2.3 cards 字段格式（逐卡片）

#### scholar.profile

来源：`full_report.researcher`

```ts
type ScholarProfile = {
  name: string;
  abbreviated_name?: string;
  affiliation?: string;
  email?: string;
  research_fields?: string[];
  total_citations?: number;
  citations_5y?: number;
  h_index?: number;
  h_index_5y?: number;
  yearly_citations?: Record<string, number>; // year -> count
  scholar_id?: string;
  avatar?: string;       // url
  description?: string;  // short bio
};
```

#### scholar.metrics

来源：`full_report.publication_stats`

```ts
type ScholarPublicationStats = {
  total_papers: number;
  first_author_papers: number;
  first_author_percentage: number;
  first_author_citations: number;
  first_author_avg_citations: number;
  first_author_papers_list: Array<{ title: string; year: string|number; venue: string; citations: number }>; // TopK（默认 50）
  last_author_papers: number;
  last_author_percentage: number;
  top_tier_papers: number;
  top_tier_percentage: number;
  conference_distribution: Record<string, number>;
  journal_distribution: Record<string, number>;
  year_distribution: Record<string, number>;
  citation_stats: { total_citations: number; max_citations: number; avg_citations: number; median_citations: number };
  top_tier_publications: {
    conferences: Array<{ title: string; year: string|number; venue: string; citations: number; author_position: number }>; // TopK（默认 50）
    journals: Array<{ title: string; year: string|number; venue: string; citations: number; author_position: number }>; // TopK（默认 50）
  };
  most_cited_paper?: {
    title: string;
    year?: string|number;
    venue?: string;
    citations?: number;
    authors?: string[];
    url?: string;
    abstract?: string;
    arxiv_id?: string;
    doi?: string;
    is_first_author?: boolean;
  };
  paper_of_year?: {
    title: string;
    year: string|number;
    venue?: string;
    citations?: number;
    authors?: string[];
    author_position?: number;
    summary?: string;
  };
  citation_velocity?: number;
  paper_news?: ScholarNews;
};
```

#### scholar.papers

```ts
type ScholarPapersCard = {
  most_cited_paper?: ScholarPublicationStats["most_cited_paper"];
  paper_of_year?: ScholarPublicationStats["paper_of_year"];
  top_tier_publications?: ScholarPublicationStats["top_tier_publications"];
  year_distribution?: ScholarPublicationStats["year_distribution"];
  // Preview list; may grow via `card.append` before `card.completed`.
  items?: Array<{
    id: string;
    title: string;
    year?: number;
    venue?: string;
    citations?: number;
    authors?: string[];
    author_position?: number;
  }>;
};
```

#### scholar.citations

来源：`full_report.researcher` 的引用指标

```ts
type ScholarCitationsCard = {
  total_citations?: number;
  citations_5y?: number;
  h_index?: number;
  h_index_5y?: number;
  yearly_citations?: Record<string, number>;
};
```

#### scholar.coauthors

来源：`full_report.coauthor_stats`

```ts
type ScholarCoauthorsCard = {
  main_author?: string;
  total_coauthors?: number;
  collaboration_index?: number; // total_coauthors / total_papers
  top_coauthors?: Array<{
    name: string;
    coauthored_papers: number;
    best_paper?: {
      title: string;
      year?: string | number;
      venue?: string;          // 会议/期刊名（尽量归一化，可能包含年份，如 "CVPR 2023"）
      original_venue?: string; // 原始 venue 字符串（来自 Scholar 页面）
      citations?: number;
    };
  }>;
  most_frequent_collaborator?: { name: string; coauthored_papers: number; best_paper?: any };
};
```

#### scholar.role_model

```ts
type ScholarRoleModel = {
  name: string;
  institution?: string;
  position?: string;
  photo_url?: string;
  achievement?: string;
  similarity_reason?: string;
};
```

#### scholar.news

来源：`full_report.paper_news`（基于 most-cited paper）

```ts
type ScholarNews = {
  news: string;
  date: string; // YYYY-MM-DD
  description: string;
  url: string | null;
  is_fallback?: boolean;
};
```

#### scholar.level

来源：`full_report.level_info`

```ts
type ScholarLevel = {
  level_cn?: string;     // e.g. "P8"
  level_us?: string;     // e.g. "L6"
  earnings?: string;     // e.g. "200000-300000"
  justification?: string;
  evaluation_bars?: Record<string, any>; // 若存在，包含研究风格等维度评分
};
```

#### scholar.summary

来源：`full_report.critical_evaluation`（LLM 生成的 markdown 文本，支持按 section 流式增量）

流式 section（固定）：`overview / strengths / risks / questions`

```ts
type ScholarSummary = { critical_evaluation?: string };
```

---

## 3) github（GitHub 分析）

### 3.1 input 怎么填

```json
{ "content": "octocat" }
```

`content` 支持：
- GitHub login（推荐）
- GitHub profile URL（后端会解析 path 的第 1 段）
- 不规范输入（后端会尝试用 GitHub Search 解析到最可能的 login）

### 3.2 默认 cards

`profile / activity / repos / role_model / roast / summary`

### 3.3 cards 字段格式（逐卡片）

#### github.profile

来源：`full_report.user`

常见字段（简版）：

```ts
type GithubUser = {
  login: string;
  name?: string;
  bio?: string;
  avatar_url?: string;
  followers?: number;
  following?: number;
  tags?: string[];
  [k: string]: any;
};
```

#### github.activity

```ts
type GithubActivityCard = {
  overview?: {
    work_experience?: number;
    stars?: number;
    issues?: number;
    pull_requests?: number;
    repositories?: number;
    additions?: number;
    deletions?: number;
    active_days?: number;
  };
  activity?: Record<string, { pull_requests?: number; issues?: number; comments?: number; contributions?: number }>;
  code_contribution?: { total?: number; languages?: Record<string, number> };
};
```

#### github.repos

```ts
type GithubReposCard = {
  feature_project?: any;
  top_projects?: any[];
  most_valuable_pull_request?: any;
};
```

> 说明：repos 内部结构比较大且变化快，建议前端按需取字段渲染；更完整示例见：
> `server/github_analyzer/USAGE_GUIDE.md`

#### github.role_model

```ts
type GithubRoleModel = { name?: string; github?: string; similarity_score?: number; reason?: string; [k: string]: any };
```

#### github.roast

```ts
type GithubRoast = { roast?: string };
```

#### github.summary

```ts
type GithubSummary = {
  valuation_and_level?: { level?: string; salary_range?: string; total_compensation?: string; reasoning?: string; [k: string]: any };
  description?: string;
};
```

---

## 4) linkedin（领英分析）

### 4.1 input 怎么填

推荐统一用 `content`（既可传 URL，也可传人名）：

```json
{ "content": "https://www.linkedin.com/in/xxx/" }
```

或：

```json
{ "content": "John Doe" }
```

可用别名：
- `content`（推荐）
- `name` / `person_name`（人名）

### 4.2 默认 cards

`profile / skills / career / role_model / money / roast / summary`

### 4.3 cards 字段格式（逐卡片）

#### linkedin.profile

来源：`full_report.profile_data`（建议只取你要展示的字段；内部包含 `raw_profile` 原始大对象）

```ts
type LinkedinProfile = {
  name?: string;
  avatar?: string;
  about?: string;
  personal_tags?: string[];
  work_experience?: any[];
  work_experience_summary?: string;
  education?: any[];
  education_summary?: string;
  skills?: LinkedinSkills;
  role_model?: LinkedinRoleModel;
  money_analysis?: LinkedinMoney;
  roast?: string;
  career?: LinkedinCareer;
  colleagues_view?: any;
  life_well_being?: any;
  raw_profile?: any; // 原始抓取结果（字段很大，不建议前端全渲染）
};
```

#### linkedin.skills

来源：`profile_data.skills`（AI 输出，数组元素为字符串）

```ts
type LinkedinSkills = {
  industry_knowledge?: string[];
  tools_technologies?: string[];
  interpersonal_skills?: string[];
  language?: string[];
};
```

#### linkedin.career

```ts
type LinkedinCareer = {
  future_development_potential?: string;
  simplified_future_development_potential?: string;
  development_advice?: {
    past_evaluation?: string;
    simplified_past_evaluation?: string;
    future_advice?: string;
  };
};

type LinkedinCareerCard = {
  career?: LinkedinCareer;
  work_experience?: any[];
  education?: any[];
  work_experience_summary?: string;
  education_summary?: string;
};
```

#### linkedin.role_model

```ts
type LinkedinRoleModel = {
  name?: string;
  institution?: string;
  position?: string;
  photo_url?: string;
  achievement?: string;
  similarity_reason?: string;
  is_celebrity?: boolean;
  celebrity_reasoning?: string;
  [k: string]: any;
};
```

#### linkedin.money

来源：`profile_data.money_analysis`

```ts
type LinkedinMoney = {
  years_of_experience?: { years?: number; start_year?: number; calculation_basis?: string };
  level_us?: string;         // e.g. "L6"
  level_cn?: string;         // e.g. "P8"
  estimated_salary?: string; // "2000000-3000000"（不含逗号）
  explanation?: string;
};
```

#### linkedin.roast

```ts
type LinkedinRoast = { roast?: string };
```

#### linkedin.summary

```ts
type LinkedinSummary = { about?: string; personal_tags?: string[] };
```

---

## 5) twitter（X/Twitter 分析）

### 5.1 input 怎么填

```json
{ "content": "jack" }
```

`content` 支持：
- Twitter 用户名（不带 `@` / 带 `@` 都可；后端会归一化）
- profile URL（后端会解析 path）

### 5.2 默认 cards

`profile / stats / network / summary`

### 5.3 cards 字段格式（逐卡片）

> 说明：当前 Twitter 数据来自 Apify；若服务端未配置 `APIFY_API_KEY`，通常会失败并触发 `card.failed`。

#### twitter.profile

```ts
type TwitterProfileCard = {
  username?: string;
  followers_count?: number;
  followings_count?: number;
};
```

#### twitter.stats

```ts
type TwitterStatsCard = {
  followers_count?: number;
  followings_count?: number;
  verified_followers_count?: number;
};
```

#### twitter.network

```ts
type TwitterTopFollower = {
  username?: string;
  profile_image?: string;
};

type TwitterNetworkCard = {
  top_followers?: TwitterTopFollower[];
};
```

#### twitter.summary

```ts
type TwitterSummaryCard = {
  summary?: string; // 当前是 20 words 左右的内容风格/类别摘要
};
```

---

## 6) openreview（OpenReview 学术档案）

### 6.1 input 怎么填

```json
{ "content": "~FirstName_LastName1" }
```

也支持 email（由服务端解析成 profile）。

### 6.2 默认 cards

`profile / papers / summary`

### 6.3 cards 字段格式（逐卡片）

#### openreview.profile

```ts
type OpenReviewProfileCard = {
  name?: string;
  expertise_areas?: string[];
};
```

#### openreview.papers

```ts
type OpenReviewRepresentativeWork = {
  id?: string;
  title?: string;
  authors?: string[];
  abstract?: string;
  keywords?: string[];
  venue?: string;
  publication_date?: string | null; // YYYY-MM-DD
  creation_year?: number | null;
};

type OpenReviewPapersCard = {
  total_papers?: number;
  papers_last_year?: number;
  representative_work?: OpenReviewRepresentativeWork | string | null; // 可能为提示字符串（无论文等）
};
```

#### openreview.summary

```ts
type OpenReviewSummaryCard = {
  summary?: string; // 服务端拼出来的简短总结（非流式）
};
```

---

## 7) huggingface（HuggingFace 档案）

### 7.1 input 怎么填

```json
{ "content": "username" }
```

支持 profile URL（后端会解析 username）。

### 7.2 默认 cards

`profile / summary`

### 7.3 cards 字段格式（逐卡片）

> 说明：此 source 字段命名跟随 HuggingFace API（camelCase），前端不要强行改名；展示层可做映射。

#### huggingface.profile

```ts
type HuggingFaceProfileCard = {
  avatarUrl?: string;
  fullname?: string;
  numModels?: number;
  numDatasets?: number;
  numSpaces?: number;
  numPapers?: number;
  numFollowers?: number;
  numFollowing?: number;
  orgs?: any[];
  representative_work?: any; // model/dataset/space 的原始对象（结构不稳定）
};
```

#### huggingface.summary

```ts
type HuggingFaceSummaryCard = {
  fullname?: string;
  numFollowers?: number;
  representative_work?: any;
};
```

---

## 8) youtube（YouTube Channel 分析）

### 8.1 input 怎么填

```json
{ "content": "UCxxxx..." }
```

也支持：
- channel URL（`youtube.com/channel/...`）
- `youtube.com/@handle`
- `youtube.com/c/<custom>`
- 频道名称（服务端会搜索匹配，可能不稳定）

### 8.2 默认 cards

`profile / summary`

### 8.3 cards 字段格式（逐卡片）

> 说明：该 source 依赖 YouTube API key；未配置时通常会失败并触发 `card.failed`。

#### youtube.profile

```ts
type YouTubeProfileCard = {
  channel_id?: string;
  channel_name?: string;
  channel_url?: string;
  subscriber_count?: number;
  total_view_count?: number;
  video_count?: number;
};
```

#### youtube.summary

```ts
type YouTubeRepresentativeVideo = {
  video_id?: string;
  title?: string;
  thumbnail?: string;
  embed_code?: string;
};

type YouTubeSummaryCard = {
  content_summary?: string;
  representative_video?: YouTubeRepresentativeVideo | null;
  analysis_date?: string; // ISO timestamp
};
```

---

## 9) 前端渲染建议（通用）

- 卡片加载态：收到 `card.started` → 显示 skeleton/spinner
- 流式输出：收到 `card.delta` → 追加到文本区域（注意做长度裁剪/折叠）
- 最终态：收到 `card.completed` → 用 `payload` 覆盖为最终结构化数据
- 错误态：`card.failed` → 显示错误提示，同时允许其它卡继续展示
- 完成：`job.completed/job.failed` → 结束流、展示“完成/部分完成/失败”

---

## 10) 参考实现

- 浏览器联调页：`examples/analyze_gateway_playground.html`
- 浏览器联调页（更完整 UI）：`test/frontend/`
- CLI smoke：`scripts/api_tests/test_analyze_gateway.sh`
