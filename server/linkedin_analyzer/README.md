# LinkedIn Profile Analyzer

LinkedIn个人资料分析器，提供多维度AI分析和缓存功能。

## 功能特性

### 🔍 智能搜索
- 使用 Tavily API 搜索 LinkedIn 个人资料（用于“人名 → profile URL”匹配，亦用于 freeform 候选推荐）
- 智能匹配人名和LinkedIn URL
- 支持多种搜索策略

### 🕸️ 资料抓取
- 使用 Apify Actor 抓取 LinkedIn profile 结构化数据（URL → profile_data）

### 📊 多维度分析
- **角色模型推荐**: 智能判断是否为名人，推荐合适的职业榜样
- **薪资分析**: 基于职位、经验、行业的薪资水平分析
- **幽默吐槽**: 生成有趣而建设性的职业评论

### 🚀 高性能缓存
- 数据库缓存支持，减少重复API调用
- 智能数据补充，支持部分数据缺失时的自动补全
- 可配置的缓存过期时间

### 🤖 AI驱动
- 完全基于AI生成分析结果
- 支持JSON格式输出
- 多线程并行处理，提高效率

## 架构设计

### 核心组件

```
server/linkedin_analyzer/
├── analyzer.py              # 主分析器
├── role_model_service.py    # 角色模型服务
├── money_service.py         # 薪资分析服务
├── roast_service.py         # 吐槽生成服务
└── README.md               # 本文档
```

### 数据库模型

```sql
-- LinkedIn profiles表
CREATE TABLE linkedin_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    linkedin_id VARCHAR(100) NOT NULL UNIQUE,
    person_name VARCHAR(100) NOT NULL,
    linkedin_url VARCHAR(500),
    headline VARCHAR(200),
    location VARCHAR(100),
    about TEXT,
    profile_photo VARCHAR(500),
    profile_data JSON,           -- 原始LinkedIn数据
    extracted_info JSON,         -- 提取的结构化信息
    ai_analysis JSON,            -- AI分析结果
    linkedin_search_results JSON, -- 搜索结果
    last_updated DATETIME,
    created_at DATETIME
);
```

## 使用方法

### 基本使用

```python
from server.linkedin_analyzer.analyzer import LinkedInAnalyzer

# 初始化分析器
config = {
    # Apify key 可放在 config，也可用环境变量 APIFY_API_KEY
    "apify": {"api_key": "your_apify_api_key"},
    "use_cache": True,
    "cache_max_age_days": 7
}

analyzer = LinkedInAnalyzer(config)

# 分析LinkedIn个人资料
result = analyzer.get_result("John Doe")
```

### 带进度回调

```python
def progress_callback(step, message, data=None):
    print(f"Step: {step}, Message: {message}")

result = analyzer.get_result_with_progress("John Doe", progress_callback)
```

### 异步使用

```python
import asyncio

async def analyze_profile():
    result = await analyzer.analyze("John Doe")
    return result

# 运行异步分析
result = asyncio.run(analyze_profile())
```

## 配置选项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `apify.api_key` | string | - | Apify API 密钥（也支持环境变量 `APIFY_API_KEY`） |
| `use_cache` | boolean | true | 是否启用缓存 |
| `cache_max_age_days` | integer | 7 | 缓存最大保存天数 |

## 第三方依赖（外部 API）

- Tavily Search：用于“人名/描述 → LinkedIn profile URL”检索（环境变量 `TAVILY_API_KEY`）。
- Apify：用于抓取 LinkedIn profile 原始数据（环境变量 `APIFY_API_KEY`；代码内使用固定 Actor）。
- OpenRouter（LLM）：用于大部分 AI 文本/结构化分析（环境变量 `OPENROUTER_API_KEY` 或 `GENERIC_OPENROUTER_API_KEY`）。
- Moonshot / Kimi（LLM）：用于部分评分、PK roast 等（环境变量 `KIMI_API_KEY`）。

## AI分析维度

### 1. 角色模型分析 (Role Model)

**名人判断逻辑**:
- 检查是否为高知名度人物（CEO、CTO、创始人等）
- 评估行业影响力和媒体曝光度
- 分析成就和奖项

**推荐策略**:
- 如果是名人：使用自己的信息作为角色模型
- 如果不是名人：推荐3个相似职业路径的知名人物

### 2. 薪资分析 (Money Analysis)

**分析维度**:
- 基于职位、经验、行业的薪资范围
- 市场定位和百分位排名
- 增长潜力和发展建议

**AI输出格式**:
```json
{
    "salary_range": {
        "min": 80000,
        "max": 120000,
        "currency": "USD",
        "description": "Salary range explanation"
    }
}
```

### 3. 幽默吐槽 (Roast)

**生成策略**:
- 基于LinkedIn资料特征生成幽默评论
- 保持友好和建设性的语调
- 避免刻薄或冒犯性内容

## 缓存机制

### 缓存策略

1. **智能缓存检查**: 分析前检查是否存在有效缓存
2. **数据验证**: 验证缓存数据的完整性
3. **部分补充**: 支持缺失AI分析数据的自动补充
4. **缓存更新**: 自动更新过期的缓存数据

### 缓存键生成

```python
# 基于LinkedIn URL
linkedin_id = f"linkedin:{linkedin_username}"

# 基于人名（备用）
linkedin_id = f"linkedin:name:{person_name.lower().replace(' ', '_')}"
```

### 缓存数据格式

```json
{
    "linkedin_id": "linkedin:john-doe",
    "person_name": "John Doe",
    "profile_data": {...},
    "extracted_info": {...},
    "ai_analysis": {
        "role_model": {...},
        "money_analysis": {...},
        "roast": "..."
    },
    "linkedin_search_results": [...],
    "_from_cache": true
}
```

## 错误处理

### 容错机制

1. **API失败回退**: 外部API失败时使用默认数据
2. **AI分析回退**: AI调用失败时生成基础分析
3. **缓存回退**: 缓存不可用时直接进行完整分析
4. **进度回调**: 实时反馈分析进度和错误状态

### 日志记录

- 使用结构化日志记录所有操作
- 支持trace ID传播
- 详细的错误追踪和调试信息

## 性能优化

### 并行处理

- 三个AI分析服务并行执行
- 使用ThreadPoolExecutor管理线程池
- 支持异步操作和进度回调

### 缓存优化

- 数据库索引优化
- 智能缓存失效策略
- 部分数据更新支持

## 扩展性

### 添加新的AI分析维度

1. 创建新的服务模块（如`skills_service.py`）
2. 在`analyzer.py`中添加并行任务
3. 更新数据库模型和缓存逻辑

### 自定义缓存策略

- 支持自定义缓存过期时间
- 可配置的缓存验证规则
- 灵活的缓存更新策略

## 依赖项

### 必需依赖

- `requests`: HTTP请求
- `tavily`: LinkedIn URL搜索
- `sqlalchemy`: 数据库操作
- `asyncio`: 异步处理

### 可选依赖

- `json_repair`: JSON修复（有回退机制）
- `server.utils.trace_context`: 追踪上下文（有回退机制）

## 部署说明

### 环境变量

```bash
export TAVILY_API_KEY="your_tavily_api_key"
export SCRAPINGDOG_API_KEY="your_scrapingdog_api_key"
```

### 数据库迁移

```bash
# 创建LinkedIn profiles表
mysql -u username -p database_name < migrations/create_linkedin_profiles_table.sql
```

### 配置示例

```python
config = {
    "tavily": {
        "api_key": os.environ.get("TAVILY_API_KEY")
    },
    "scrapingdog": {
        "api_key": os.environ.get("SCRAPINGDOG_API_KEY")
    },
    "use_cache": True,
    "cache_max_age_days": 7
}
```

## 监控和维护

### 缓存统计

```python
from src.utils.linkedin_cache import get_linkedin_cache_stats

stats = get_linkedin_cache_stats()
print(f"Total records: {stats['total_records']}")
print(f"Recent records (24h): {stats['recent_records_24h']}")
```

### 缓存清理

```python
from src.utils.linkedin_cache import clear_linkedin_cache

# 清理特定记录
clear_linkedin_cache("linkedin:john-doe")

# 清理所有缓存
clear_linkedin_cache()
```

## 故障排除

### 常见问题

1. **API密钥错误**: 检查环境变量和配置
2. **缓存连接失败**: 检查数据库连接
3. **AI分析超时**: 调整超时设置和重试机制
4. **内存使用过高**: 优化缓存策略和数据清理

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 启用详细日志
logger = logging.getLogger('server.linkedin_analyzer')
logger.setLevel(logging.DEBUG)
```

## 更新日志

### v1.0.0
- 初始版本发布
- 支持基本的LinkedIn分析功能
- 实现缓存机制
- 添加名人判断逻辑
- 支持多线程并行处理 
