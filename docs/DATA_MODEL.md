# Scholar 服务数据模型说明

本文档详细说明了 Scholar 服务中使用的数据模型和各字段的含义。

## 研究者基本信息 (researcher)

| 参数 | 详细含义 |
|------|----------|
| `name` | 研究者的全名，从 Google Scholar 个人资料中获取 |
| `abbreviated_name` | 研究者的缩写名称，通常为"首字母 姓氏"的格式，如"P Lin" |
| `affiliation` | 研究者当前所属的机构或大学 |
| `email` | 研究者的电子邮件地址（如果在 Google Scholar 上公开） |
| `research_fields` | 研究者的研究领域列表，从 Google Scholar 个人资料中的兴趣标签获取 |
| `total_citations` | 研究者所有论文的总引用次数 |
| `citations_5y` | 研究者过去 5 年内的总引用次数 |
| `h_index` | 研究者的 h 指数，表示有 h 篇论文至少被引用了 h 次 |
| `h_index_5y` | 研究者过去 5 年内的 h 指数 |
| `yearly_citations` | 按年份统计的引用次数，格式为 `{年份: 引用次数}` |

## 发表论文统计 (publication_stats)

| 参数 | 详细含义 |
|------|----------|
| `total_papers` | 研究者发表的论文总数 |
| `first_author_papers` | 研究者作为第一作者的论文数量 |
| `first_author_percentage` | 第一作者论文占总论文的百分比 |
| `first_author_citations` | 研究者作为第一作者的论文获得的总引用次数 |
| `first_author_papers_list` | 研究者作为第一作者的论文详细列表 |
| `first_author_avg_citations` | 研究者作为第一作者的论文平均引用次数 |
| `last_author_papers` | 研究者作为最后作者（通常是通讯作者）的论文数量 |
| `last_author_percentage` | 最后作者论文占总论文的百分比 |
| `top_tier_papers` | 发表在顶级会议或期刊上的论文数量 |
| `top_tier_percentage` | 顶级会议/期刊论文占总论文的百分比 |
| `conference_distribution` | 按会议统计的论文分布，格式为 `{会议名称: 论文数量}` |
| `journal_distribution` | 按期刊统计的论文分布，格式为 `{期刊名称: 论文数量}` |
| `year_distribution` | 按年份统计的论文分布，格式为 `{年份: 论文数量}` |
| `citation_stats` | 引用统计信息，包括总引用、最高引用、平均引用和中位数引用 |
| `top_tier_publications` | 顶级会议和期刊发表的论文详细信息 |
| `most_cited_paper` | 被引用次数最多的论文详细信息 |
| `citation_velocity` | 引用增长速度，基于最近 3 年的引用增长率计算 |

## 论文详细信息

| 参数 | 详细含义 |
|------|----------|
| `title` | 论文标题 |
| `year` | 发表年份 |
| `venue` | 发表的会议或期刊名称 |
| `citations` | 被引用次数 |
| `authors` | 作者列表 |
| `author_position` | 研究者在作者列表中的位置（1 表示第一作者） |

## 合作者统计 (coauthor_stats)

| 参数 | 详细含义 |
|------|----------|
| `total_coauthors` | 研究者的合作者总数 |
| `top_coauthors` | 最常合作的合作者列表（按合作论文数量排序） |
| `collaboration_index` | 合作指数，计算为合作者数量除以论文数量 |

## 最常合作者信息 (most_frequent_collaborator)

| 参数 | 详细含义 |
|------|----------|
| `full_name` | 合作者的全名 |
| `affiliation` | 合作者所属的机构或大学 |
| `research_interests` | 合作者的研究兴趣领域 |
| `scholar_id` | 合作者的 Google Scholar ID |
| `coauthored_papers` | 与研究者合作发表的论文数量 |
| `best_paper` | 与该合作者合作的引用最高的论文 |
| `h_index` | 合作者的 h 指数（如果可获取） |
| `total_citations` | 合作者的总引用次数（如果可获取） |

## 研究者评级 (rating)

| 参数 | 详细含义 |
|------|----------|
| `h_index_score` | 基于 h 指数的评分（1-10 分） |
| `citation_score` | 基于总引用次数的评分（1-10 分） |
| `publication_score` | 基于发表论文数量的评分（1-10 分） |
| `top_tier_score` | 基于顶级会议/期刊论文数量的评分（1-10 分） |
| `first_author_score` | 基于第一作者论文数量和比例的评分（1-10 分） |
| `overall_score` | 综合评分，各项评分的加权平均 |
| `level` | 根据综合评分确定的研究者级别（如"Distinguished Researcher"、"Senior Researcher"等） |

## 角色模型 (role_model)

| 参数 | 详细含义 |
|------|----------|
| `name` | 角色模型的姓名 |
| `institution` | 角色模型所属的机构或大学 |
| `position` | 角色模型的职位（如教授、研究员等） |
| `photo_url` | 角色模型的照片 URL |
| `achievement` | 角色模型的主要成就 |
| `similarity_reason` | 角色模型与研究者相似的原因 |

## 职业水平评估 (level_info)

| 参数 | 详细含义 |
|------|----------|
| `years_of_experience` | 工作经验年限信息，包括年数、起始年份和计算依据 |
| `level_us` | 在美国科技公司（如 Google）的对应级别，如 L5、L6 等 |
| `level_cn` | 在中国科技公司（如阿里巴巴）的对应级别，如 P6、P7 等 |
| `earnings` | 预估年薪（包括基本工资、奖金和股票） |
| `justification` | 评估理由，解释为什么研究者被评为该级别 |

## 研究风格评估 (evaluation_bars)

| 参数 | 详细含义 |
|------|----------|
| `depth_vs_breadth` | 研究深度与广度的评分（0-10，0 表示非常广泛，10 表示非常深入） |
| `theory_vs_practice` | 理论与实践的评分（0-10，0 表示非常实用，10 表示非常理论） |
| `individual_vs_team` | 个人与团队的评分（0-10，0 表示非常个人化，10 表示非常团队导向） |

## 最被引用论文相关新闻 (news_info)

| 参数 | 详细含义 |
|------|----------|
| `news` | 新闻标题 |
| `date` | 新闻发布日期 |
| `description` | 新闻描述或摘要 |
| `url` | 新闻链接 |
