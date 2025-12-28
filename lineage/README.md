### Academic Lineage

- date: 20250430-0501
- func: 解决的是找到和显示某个人一度人脉中最NB的人(最多3个), 二度人脉中最NB的人(最多3个), 以及和师承派系等内容(和Yann Lecun, Yoshua Bengio, Geoffery Hinton?)
- source: OpenReview


#### 1. 流程

a) 用户输入Openreview, 或者我们根据名字or Google Scholar ID, 找到Openreview, 进行爬虫: 爬取Advisors, Relations & Conflicts字段. Co-Authors字段. @Sam √

b) 根据字段, 写prompt, 要求Agent or 大模型输出Academic Lineage(必须都要有Google Scholar ID, 这样就能无缝的进入我们的分析页面了). @Sam √

*有不少学者的openreview查不到其google scholar id. -> 过滤掉, 用coauthors里面用openreview的 -> google scholar id查询这个先不做(不准&怕出问题, 为何智谱不直接支持呢? 肯定有一些合规的部分). (20250501)
**头像, 这里不好放假的头像. -> Google Scholar 头像获取, (20250501)

c) 好看的呈现 & UI兼容: @Mark

***递归和呈现形式. (20250501)


#### 2. Harrison (完整对接+上线)

- a) 优化速度, 完整度, 检索准确度.
- b) 扩大搜索范围: 整个顶会的OpenReview库.
- c) Bonus: 配对, 搞抽象.
