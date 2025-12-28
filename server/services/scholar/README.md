# Scholar 服务模块

## 简介

Scholar 服务模块是一个用于分析学术研究者在 Google Scholar 上的学术表现的工具。该模块通过爬取和分析 Google Scholar 的数据，生成关于研究者的全面报告，包括发表论文统计、引用情况、合作者网络、顶级会议/期刊发表情况等。

## 模块结构

该模块采用模块化设计，将不同功能拆分为独立的组件，提高代码的可维护性和可扩展性：

1. **config.py**: 配置文件，包含顶级会议和期刊列表
2. **data_fetcher.py**: 数据获取模块，负责从 Google Scholar 获取研究者数据
3. **analyzer.py**: 数据分析模块，负责分析研究者的论文和合作者数据
4. **visualizer.py**: 可视化模块，负责生成论文趋势和合作者网络的可视化图表
5. **scholar_service.py**: 主服务类，集成所有组件并提供完整的分析功能

## 主要功能

1. **研究者信息获取**：通过姓名或 Google Scholar ID 获取研究者的基本信息
2. **论文分析**：分析研究者的发表论文数量、引用情况、发表会议/期刊分布等
3. **合作者网络分析**：分析研究者的合作者网络，找出最频繁的合作者
4. **角色模型推荐**：根据研究者的学术表现，推荐适合的角色模型（Role Model）
5. **职业水平评估**：评估研究者的职业水平，如在 Google 或阿里巴巴的级别、薪资范围等
6. **研究风格评估**：评估研究者的研究风格，如研究深度vs广度、理论vs实践、个人vs团队等

## 运行Demo

```bash
python server/services/scholar/scholar_service.py
```

## 使用方法

```python
from server.services.scholar.scholar_service import run_scholar_analysis

# 通过研究者姓名分析
researcher_name = "研究者姓名"
api_token = 'your_api_token'  # Crawlbase API 令牌
report = run_scholar_analysis(researcher_name=researcher_name, use_crawlbase=True, api_token=api_token)

# 通过 Google Scholar ID 分析
scholar_id = "XXXXXXXXXXXX"
report = run_scholar_analysis(scholar_id=scholar_id, use_crawlbase=True, api_token=api_token)
```


## 特殊逻辑说明

1. **角色模型处理**：当研究者自己就是角色模型或找不到合适的角色模型时，`get_template_figure` 函数会返回 `None`。在显示时会提示 "No role model found or role model is himself"。

2. **合作者信息处理**：为了避免因缺少 `h_index` 和 `total_citations` 字段导致的错误，代码会为这些字段提供默认值 'N/A'。

3. **职业评估信息处理**：职业评估信息包括工作年限（YoE）、职业级别（Google L级别和阿里巴巴 P级别）、预估薪资和研究风格评估。代码使用 `.get()` 方法安全地获取这些可能缺失的字段。

4. **引用计数比较**：在比较论文引用数时，代码会将字符串类型的引用数转换为整数，以确保正确比较。

## 依赖库

- scholarly: 用于访问 Google Scholar API
- crawlbase: 用于绕过 Google Scholar 的访问限制
- BeautifulSoup: 用于解析 HTML 内容
- networkx: 用于生成和分析合作者网络
- matplotlib/seaborn: 用于数据可视化
- pandas/numpy: 用于数据处理和分析

## 注意事项

1. Google Scholar 有访问限制，频繁访问可能导致 IP 被封。建议使用 Crawlbase 代理服务。
2. 分析大量数据可能需要较长时间，特别是对于有大量论文的研究者。
3. 角色模型和职业评估功能依赖于外部 API，可能会受到网络和 API 可用性的影响。
