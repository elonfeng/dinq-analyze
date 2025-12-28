# 学者信息处理流程文档

本文档详细描述了系统获取和处理学者信息的完整流程，包括数据获取、分析、转换和展示各个阶段。

## 1. 学者信息获取与报告生成流程

### 1.1 `generate_report` 函数流程

`ScholarService.generate_report` 函数是获取学者信息的核心入口，接收学者姓名或 Google Scholar ID 作为输入，返回完整的学者分析报告。

#### 步骤 1: 输入验证与缓存检查
- 验证输入参数（必须提供学者姓名或 Scholar ID）
- 如果启用缓存且提供了 Scholar ID，尝试从缓存获取数据
- 如果找到有效的缓存数据，直接返回

#### 步骤 2: 搜索学者
- 使用 `ScholarDataFetcher.search_researcher` 方法搜索学者
- 根据提供的姓名或 Scholar ID 查找学者信息
- 如果找不到学者，返回 None

#### 步骤 3: 获取完整资料
- 使用 `ScholarDataFetcher.get_full_profile` 方法获取学者的完整资料
- 包括基本信息、论文列表、引用数据等
- 如果无法获取完整资料，返回 None

#### 步骤 4: 分析论文
- 使用 `ScholarAnalyzer.analyze_publications` 方法分析学者的论文
- 计算论文总数、引用总数、年度分布、会议分布等统计信息
- 识别最具代表性的论文（引用最多的论文）

#### 步骤 5: 分析合作者
- 使用 `ScholarAnalyzer.analyze_coauthors` 方法分析学者的合作者
- 统计合作者数量、合作频率
- 识别最频繁合作的合作者

#### 步骤 6: 计算学者评级
- 使用 `ScholarAnalyzer.calculate_researcher_rating` 方法计算学者评级
- 基于 h 指数、引用数、论文数等指标
- 生成学者的整体评级和研究水平

#### 步骤 7: 获取最佳合作者
- 使用 `get_best_collaborator` 函数获取最佳合作者的详细信息
- 确保最佳合作者不是学者自己（使用多种方法检查）
- 如果需要，在更多合作者中查找替代者

#### 步骤 8: 生成随机头像和描述
- 为学者生成随机头像和描述
- 使用 `get_random_avatar` 和 `get_random_description` 函数

#### 步骤 9: 编译报告
- 将所有收集到的信息整合到一个结构化的报告中
- 包括学者基本信息、论文统计、合作者信息等

#### 步骤 10: 获取角色模型
- 使用 `get_role_model` 函数获取学者的角色模型
- 如果找不到合适的角色模型，使用学者自己作为角色模型

#### 步骤 11: 生成学者评价
- 使用 `generate_critical_evaluation` 函数生成学者的批判性评价
- 添加到报告中

#### 步骤 12: 缓存结果
- 如果启用缓存且有 Scholar ID，将数据保存到缓存
- 便于后续快速访问

### 1.2 获取的学者信息字段

通过 `generate_report` 函数，系统获取以下学者信息：

#### 基本信息
- 姓名 (`name`)
- 缩写名称 (`abbreviated_name`)
- 所属机构 (`affiliation`)
- 电子邮件 (`email`)
- 研究领域 (`research_fields`)
- 总引用次数 (`total_citations`)
- 近 5 年引用次数 (`citations_5y`)
- h 指数 (`h_index`)
- 近 5 年 h 指数 (`h_index_5y`)
- 年度引用次数 (`yearly_citations`)
- Google Scholar ID (`scholar_id`)
- 头像 URL (`avatar`)
- 描述 (`description`)

#### 职级和薪资信息
- 工作经验年限 (`years_of_experience`)
  - 年数 (`years`)
  - 起始年份 (`start_year`)
  - 计算依据 (`calculation_basis`)
- 美国职级 (`level_us`)，如 "L7"
- 中国职级 (`level_cn`)，如 "P9"
- 年薪估计 (`earnings`)，如 "1500000"
- 评估理由 (`justification`)

#### 研究风格评估
- 研究深度与广度 (`depth_vs_breadth`)
  - 评分 (`score`)，0-10 分
  - 解释 (`explanation`)
- 理论与实践 (`theory_vs_practice`)
  - 评分 (`score`)，0-10 分
  - 解释 (`explanation`)
- 个人与团队 (`individual_vs_team`)
  - 评分 (`score`)，0-10 分
  - 解释 (`explanation`)

#### 论文统计
- 论文总数 (`total_papers`)
- 引用总数 (`total_citations`)
- h 指数 (`h_index`)
- 年度引用次数 (`yearly_citations`)
- 年度论文数量 (`yearly_papers`)
- 顶级会议论文数量 (`top_tier_papers`)
- 第一作者论文数量 (`first_author_papers`)
- 第一作者引用次数 (`first_author_citations`)
- 最后作者论文数量 (`last_author_papers`)
- 会议分布 (`conference_distribution`)

#### 合作者信息
- 合作者总数 (`total_coauthors`)
- 最佳合作者信息
  - 全名 (`full_name`)
  - 所属机构 (`affiliation`)
  - 研究兴趣 (`research_interests`)
  - Scholar ID (`scholar_id`)
  - 合作论文数量 (`coauthored_papers`)
  - 最佳合作论文 (`best_paper`)
  - 头像 (`avatar`)

#### 代表性论文
- 标题 (`title`)
- 年份 (`year`)
- 会议/期刊 (`venue`)
- 引用次数 (`citations`)
- 作者位置 (`author_position`)
- 相关新闻 (`paper_news`)

#### 角色模型
- 姓名 (`name`)
- 机构 (`institution`)
- 职位 (`position`)
- 照片 URL (`photo_url`)
- 成就 (`achievement`)
- 相似性原因 (`similarity_reason`)

#### 学者评价
- 批判性评价 (`critical_evaluation`)

## 2. 学者分析流程 (`run_scholar_analysis`)

`run_scholar_analysis` 函数是学者分析的核心流程，它调用 `generate_report` 获取基础数据，然后进行进一步处理和丰富。

### 2.1 基本流程

#### 步骤 1: 初始化服务
- 创建 `ScholarService` 实例
- 配置是否使用 Crawlbase API、缓存等

#### 步骤 2: 报告初始状态
- 使用 `report_initial_status` 函数报告分析开始

#### 步骤 3: 获取 Scholar ID（如果未提供）
- 如果只提供了学者姓名，使用 `get_scholar_information` 函数获取 Scholar ID
- 限制学者名称长度，防止上下文长度超限

#### 步骤 4: 生成报告
- 调用 `ScholarService.generate_report` 函数生成基础报告
- 记录数据是否来自缓存

#### 步骤 5: 报告分析完成
- 使用 `report_analysis_completion` 函数报告分析完成
- 包括耗时信息

#### 步骤 6: 报告基本学者信息
- 使用 `report_basic_researcher_info` 函数报告学者基本信息

#### 步骤 7: 处理最具引用论文
- 从报告中获取最具引用论文信息
- 如果没有，创建默认的空论文信息
- 使用 `report_most_cited_paper` 函数报告最具引用论文信息

#### 步骤 8: 查找 arXiv 信息
- 如果数据不是来自缓存，使用 `find_arxiv` 函数查找论文的 arXiv 信息
- 将结果保存到报告中

#### 步骤 9: 获取论文相关新闻
- 如果数据不是来自缓存，使用 `get_latest_news` 函数获取论文相关新闻
- 使用 `report_paper_news` 函数报告论文新闻

#### 步骤 10: 报告最佳合作者信息
- 使用 `report_collaborator_info` 函数报告最佳合作者信息

#### 步骤 11: 获取角色模型信息
- 如果数据不是来自缓存，使用 `get_role_model` 函数获取角色模型信息
- 使用 `report_role_model_info` 函数报告角色模型信息

#### 步骤 12: 获取职级和薪资信息
- 使用 `get_career_level_info` 函数获取职级和薪资信息
- 该函数调用 `three_card_juris_people` 函数，通过 OpenRouter API 的 GPT-4o 模型分析学者资料
- 使用 `report_career_level_info` 函数报告职级和薪资信息

### 2.2 状态报告功能

在分析过程中，系统使用以下函数报告状态：

- `report_initial_status`: 报告分析开始
- `report_analysis_completion`: 报告分析完成
- `report_basic_researcher_info`: 报告基本学者信息
- `report_most_cited_paper`: 报告最具引用论文信息
- `report_paper_news`: 报告论文新闻
- `report_collaborator_info`: 报告最佳合作者信息
- `report_role_model_info`: 报告角色模型信息
- `report_career_level_info`: 报告职级信息

这些函数通过回调机制将状态信息传递给调用者，便于实时显示分析进度。

## 3. 报告保存与转换流程

### 3.1 报告保存流程

`save_scholar_report` 函数负责保存学者报告并生成格式化的 JSON 文件：

#### 步骤 1: 创建报告目录
- 确保 `reports` 目录存在

#### 步骤 2: 获取学者信息
- 从报告中获取学者姓名和 Scholar ID
- 如果没有 Scholar ID，使用时间戳作为备用

#### 步骤 3: 生成文件名
- 使用学者姓名和 Scholar ID 生成文件名

#### 步骤 4: 保存原始 JSON 文件
- 将报告保存为 JSON 文件

#### 步骤 5: 转换数据格式
- 使用 `transform_data` 函数转换数据格式
- 保存转换后的 JSON 文件

#### 步骤 6: 生成 URL
- 根据环境变量选择不同的域名
- 生成 JSON 文件的 URL

### 3.2 数据转换流程

`transform_data` 函数负责将原始报告数据转换为前端所需的格式：

#### 步骤 1: 初始化目标数据结构
- 创建符合前端要求的数据结构

#### 步骤 2: 填充学者信息
- 从原始数据中提取学者基本信息
- 添加头像和描述
- 清理数值字段

#### 步骤 3: 填充论文统计信息
- 从原始数据中提取论文统计信息
- 清理数值字段

#### 步骤 4: 填充论文洞察信息
- 从原始数据中提取论文洞察信息
- 精简会议分布信息

#### 步骤 5: 填充角色模型信息
- 从原始数据中提取角色模型信息
- 如果没有有效的角色模型，创建以自己为角色模型

#### 步骤 6: 填充最佳合作者信息
- 从原始数据中提取最佳合作者信息
- 添加头像
- 处理最佳合作论文信息

#### 步骤 7: 填充其他信息
- 填充职级信息
- 填充研究者特征信息
- 填充代表性论文信息
- 填充批判性评价信息

## 4. 职级和薪资信息处理流程

系统使用专门的模块处理学者的职级和薪资信息：

### 4.1 职级信息获取流程

`get_career_level_info` 函数是获取学者职级信息的入口：

#### 步骤 1: 检查缓存
- 如果数据来自缓存且已包含职级信息，直接使用缓存数据
- 否则，进行实时计算

#### 步骤 2: 获取职级信息
- 检查报告中是否有足够的数据来生成职级信息
- 如果有，调用 `three_card_juris_people` 函数获取职级信息
- 如果没有，创建默认的职级信息

#### 步骤 3: 处理研究风格信息
- 从职级信息中提取研究风格数据
- 添加到报告中

#### 步骤 4: 保存结果
- 将职级信息保存到报告中，便于缓存

### 4.2 职级评估流程

`three_card_juris_people` 函数负责评估学者的职级和薪资：

#### 步骤 1: 格式化和清理数据
- 将学者信息格式化为文本
- 清理数据，确保兼容性

#### 步骤 2: 构建提示词
- 使用 `get_salary_evaluation_prompt` 函数构建提示词
- 提示词包含评估职级、薪资和研究风格的指导

#### 步骤 3: 调用 OpenRouter API
- 使用 OpenRouter 的 GPT-4o 模型
- 发送请求并获取响应

#### 步骤 4: 解析响应
- 解析 JSON 响应
- 提取职级、薪资和研究风格信息

#### 步骤 5: 构建返回结果
- 包含工作经验年限 (`years_of_experience`)
- 包含美国职级 (`level_us`)，如 "L7"
- 包含中国职级 (`level_cn`)，如 "P9"
- 包含年薪估计 (`earnings`)，如 "1500000"
- 包含评估理由 (`justification`)
- 包含研究风格评估 (`evaluation_bars`)
  - 研究深度与广度 (`depth_vs_breadth`)
  - 理论与实践 (`theory_vs_practice`)
  - 个人与团队 (`individual_vs_team`)

### 4.3 研究风格处理流程

`process_research_style` 函数负责从职级信息中提取研究风格数据：

#### 步骤 1: 检查评估数据
- 检查职级信息中是否包含 `evaluation_bars` 数据

#### 步骤 2: 创建研究风格字典
- 提取深度与广度评分
- 提取理论与实践评分
- 提取个人与团队评分
- 提取评估理由

#### 步骤 3: 设置到报告中
- 将研究风格字典添加到报告中

## 5. 数据处理辅助函数

系统使用多个辅助函数处理数据：

### 5.1 数值清理函数

`clean_number` 函数用于清理和转换数值：
- 处理各种格式的数值字符串
- 处理带有货币符号的字符串
- 处理范围值（如 "300,000-400,000 USD"）
- 处理科学计数法

### 5.2 年份清理函数

`clean_year` 函数用于清理和转换年份：
- 将各种格式的年份字符串转换为整数

### 5.3 会议处理函数

`clean_arxiv_venue` 函数用于处理 arXiv 格式的会议字符串：
- 提取 arXiv ID
- 提取年份
- 构建清理后的格式

`simplify_venue` 函数用于简化会议名称：
- 提取已知会议的缩写
- 处理常见的会议名称变体

`refine_conference_distribution` 函数用于精简会议分布：
- 只保留首选缩写
- 将 arXiv 和其他会议归类为 "Others"

## 6. 总结

学者信息处理流程是一个复杂的多阶段过程，包括：

1. **数据获取**：通过 Google Scholar 获取学者的基本信息和论文列表
2. **数据分析**：分析学者的论文、合作者、引用情况等
3. **数据丰富**：添加角色模型、职级信息、薪资估计、研究风格评估、批判性评价等
4. **数据转换**：将原始数据转换为前端所需的格式
5. **数据保存**：保存原始和转换后的数据，便于后续访问

这个流程确保了系统能够提供全面、准确的学者信息，支持各种学术分析和可视化功能。特别是，系统能够基于学者的学术成就和影响力，提供职级、薪资和研究风格的评估，帮助用户更全面地了解学者的学术地位和价值。
