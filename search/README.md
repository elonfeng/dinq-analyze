# ICLR/ICML/NeurIPS 2025/2024 论文检索系统

这是一个基于 ICLR 2025 提交论文数据的检索增强生成（RAG）系统，可以根据用户查询自动定位相关论文及其作者信息。

## 功能特点

- 基于语义相似度搜索论文
- 返回最相关的论文及其作者信息
- 提供完整论文详情查看功能
- 交互式命令行界面
- 支持多种向量搜索后端 (FAISS 和 USearch)

## 安装

1. 确保已安装 Python 3.8 或更高版本
2. 安装所需依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

1. 运行程序：

```bash
# 使用FAISS向量搜索 (较慢但更精确)
python analysis.py

# 使用USearch向量搜索 (更快速)
python analysis_usearch.py
```

2. 在提示符下输入您的查询（例如研究主题、技术、作者名等）
3. 系统将返回最相关的论文列表
4. 输入论文编号查看完整详情，或直接按 Enter 进行新的搜索
5. 输入 'exit' 退出程序

## 性能比较

- **FAISS**: 完整精度的向量搜索，适合中小型数据集和精确匹配需求
- **USearch**: 近似最近邻搜索，速度更快，内存占用更少，适合大型数据集

## 数据来源

系统使用 `iclr/iclr2025.json` 文件中的 ICLR 2025 论文数据。

## 爬取顶会接收论文

### 1. 会议list

- ICLR 2025 https://iclr.cc/virtual/2025/papers.html
- ICML 2024 https://icml.cc/virtual/2024/papers.html
- NeurIPS 2024 https://nips.cc/virtual/2024/papers.html
- (TODO) ACM MM 2025
- (TODO) 其它用OpenReview的顶级会议: CVPR等.


### 2. 现成库

https://github.com/papercopilot/paperlists

### 3. 思考

分析获取和目标: 知识库.

- `analysis_cn.py`非常不准, 不能用中文.
- `analysis.py`替换为usearch(原本为Faiss).

(A) 要能允许多个`json`动态挂载.
(B) 能支持返回前两名作者的openreview地址: https://openreview.net/profile?id=xxx 前缀.
(C) 能够根据openreview页面, 搜寻到其google scholar的id.
(D) 调用学者分析详情页. (后端)
(E) 其它.


### 4. 完成(2025-04-25 到 2025-04-26)

鉴于很多人都提了, 如何找到人才是非常重要的部分. 从最小可行性出发, 我们从最近一年的3大顶会出发. (后续会加入更多的会议, 并及时更新最新的会议接受情况.)

提供2个功能: (都有选项: 是否只返回第一作者)

- (A) 搜索信息(用户给定一个关键词或者一句话: 我们返回相似的顶会论文作者: 作者名称, 作者职位, Google scholar, 论文题目, 论文中稿情况, 论文类别(Poster/Oral/Spotlight), 论文地址)

```
Title: LLMs Can Plan Only If We Tell Them (论文title)
Venue: ICLR 2025 (会议名称+年份)
URL: https://iclr.cc/virtual/2025/poster/30078 (论文url)

Authors:
  Name: Bilgehan Sel (作者姓名)
  OpenReview: https://openreview.net/profile?id=~Bilgehan_Sel1 (作者openreview信息)
  Tags: LLM;NLP;Agent (作者类别)
  Current: PhD student at Virginia Polytechnic Institute and State University (作者机构和职位)
  Google Scholar: https://scholar.google.com/citations?user=Gf7GHgYAAAAJ (Google Scholar -> DINQ 分析)

Relevance Score: 57 (相关得分)
```


- (B) 推荐人(随机展示三个顶会的论文的随机作者, 展示信息: 作者名称, 作者职位, Google Scholar, 论文题目, 论文中稿情况, 论文类别(Poster/Oral/Spotlight), 论文地址)

```
Recommendation #6

Author Information: (随机配个头像)
  Name: Vincent Hanke (姓名)
  OpenReview: https://openreview.net/profile?id=~Vincent_Hanke1 (Openreview链接)
  Google Scholar: https://scholar.google.com/citations?user=QAilX5kAAAAJ (GS链接->调用我们的学者分析)
  Current: PhD student, CISPA Helmholtz Center for Information Security (职位和机构, 有的字段没有则前端不应该显示)
  Research Tags: LLM;Security;ML (研究领域Hashtag)

Paper Information:
  Title: Open LLMs are Necessary for Current Private Adaptations and Outperform their Closed Alternatives (论文名称)
  Status: Poster (类型: Poster/Oral/Spotlight这几种)
  Venue: NEURIPS 2024 (顶会名称和年份: NeurIPS显示紫色, ICLR显示绿色, ICML显示红色, 目前就这三个会议)
  URL: https://neurips.cc/virtual/2024/poster/95707 (论文的Url)
```


TODO: 

1. 提前挂载好iclr2025.json这种文件, 这样(A)和(B)功能可以减轻延时.
2. A功能偶尔会错误, 需要重试.
3. A功能加速(Bonus).
