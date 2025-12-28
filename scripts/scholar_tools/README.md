# Google Scholar 学者资料获取和分析工具

这个目录包含了一组用于获取和分析 Google Scholar 学者资料的工具。

## 脚本说明

1. **fetch_full_scholar_profile.py** - 获取学者的完整个人资料，包括最多 500 篇论文
   - 在第一页获取完整的个人资料信息，后续页面只获取论文信息
   - 支持使用 Crawlbase API 绕过 Google Scholar 的限制（可选）

2. **analyze_scholar_profile.py** - 分析获取到的学者个人资料
   - 生成各种统计信息，如论文年份分布、引用次数分布等
   - 找出引用次数最多的论文
   - 找出最常合作的作者
   - 找出最常发表的期刊/会议
   - 生成可视化图表，保存到 `visualizations` 目录

3. **run_scholar_analysis.sh** - 一键运行上述两个脚本
   - 自动检查并安装必要的 Python 包
   - 支持各种命令行参数，如指定学者 ID、最大论文数量等

4. **test_cache_validator.py** - 测试缓存验证器
   - 从缓存中获取学者数据
   - 验证并补全缓存数据
   - 将验证后的数据保存到文件
   - 用于检查和修复缓存中的无效或不完整数据

5. **test_research_style.py** - 测试研究风格评估
   - 从缓存中获取学者数据
   - 评估学者的研究风格，包括深度与广度、理论与实践、个人与团队三个维度
   - 输出详细的评估结果和解释
   - 可以将结果保存到JSON文件

## 使用方法

### 一键运行（推荐）

```bash
./run_scholar_analysis.sh
```

这将使用默认参数（学者 ID: 0VAe-TQAAAAJ，最大论文数量: 500）运行脚本。

### 自定义参数

```bash
./run_scholar_analysis.sh --id SCHOLAR_ID --max-papers NUMBER --output OUTPUT_FILE
```

参数说明：
- `--id SCHOLAR_ID`: 指定 Google Scholar ID（默认: 0VAe-TQAAAAJ）
- `--max-papers NUMBER`: 最大论文数量（默认: 500）
- `--output FILE`: 输出文件名（默认: scholar_profile.json）
- `--no-crawlbase`: 不使用 Crawlbase API
- `--token TOKEN`: 指定 Crawlbase API 令牌

### 单独运行脚本

1. 获取学者资料：
   ```bash
   python3 fetch_full_scholar_profile.py SCHOLAR_ID --max-papers 500
   ```

2. 分析学者资料：
   ```bash
   python3 analyze_scholar_profile.py scholar_profile.json
   ```

### 测试缓存验证器

```bash
python3 test_cache_validator.py SCHOLAR_ID
```

参数说明：
- `SCHOLAR_ID`: 指定 Google Scholar ID
- `--max-age-days DAYS`: 缓存最大有效期（天）（默认: 3）
- `--no-crawlbase`: 不使用 Crawlbase API
- `--api-token TOKEN`: 指定 Crawlbase API 令牌

### 测试研究风格评估

```bash
python3 test_research_style.py SCHOLAR_ID
```

参数说明：
- `SCHOLAR_ID`: 指定 Google Scholar ID
- `--output FILE`: 输出文件名（可选）

## 依赖项

- Python 3.6+
- requests
- beautifulsoup4
- matplotlib

`run_scholar_analysis.sh` 脚本会自动检查并安装这些依赖项。

## 注意事项

1. Google Scholar 可能会限制频繁的请求，建议使用 Crawlbase API 或添加适当的延迟
2. 脚本已经添加了延迟（每次请求之间等待 3 秒），以避免被封
3. 输出文件会保存在当前目录，可视化图表会保存到 `visualizations` 目录
