# 学者服务测试套件

本目录包含用于测试学者服务（Scholar Service）各个组件和功能的测试脚本。这些脚本可以帮助您验证学者服务的各个步骤是否正常工作，并且可以在不同的场景下进行测试。

## 目录

- [测试脚本概述](#测试脚本概述)
- [测试步骤说明](#测试步骤说明)
- [使用方法](#使用方法)
  - [测试单个学者](#测试单个学者)
  - [测试单个学者的所有步骤](#测试单个学者的所有步骤)
  - [测试单个学者的特定步骤](#测试单个学者的特定步骤)
  - [批量测试特定步骤](#批量测试特定步骤)
  - [批量测试学者](#批量测试学者)
  - [运行所有测试](#运行所有测试)
- [测试结果](#测试结果)
- [常见问题](#常见问题)

## 测试脚本概述

本测试套件包含以下脚本：

1. **test_single_scholar.py**
   - 用于测试单个学者的完整学者服务流程
   - 可以通过名称、ID或URL指定学者

2. **test_all_steps_single_scholar.py**
   - 对单个学者运行所有步骤的测试
   - 每个步骤的结果都会保存到单独的文件中

3. **test_specific_step.py**
   - 针对单个学者运行特定步骤的测试
   - 支持所有12个步骤的单独测试

4. **batch_run_step.py**
   - 批量运行特定步骤的测试
   - 可以从测试文件中读取多个学者信息

5. **batch_test_scholars.py**
   - 更强大的批量测试脚本
   - 支持多种测试类型（完整测试、所有步骤测试、特定步骤测试）
   - 支持并行测试、超时控制等高级功能

6. **run_all_tests.sh**
   - 一键运行所有测试的Shell脚本
   - 包括完整测试、所有步骤测试和各个步骤的单独测试

7. **0416测试.txt**
   - 包含多个学者的测试数据
   - 每行包含一个学者的名称和Google Scholar URL

8. **quick_test.txt**
   - 包含少量学者的测试数据，用于快速测试

## 测试步骤说明

学者服务的处理流程被分解为以下12个步骤，每个步骤都可以单独测试：

1. **步骤1**: 搜索学者
   - 根据名称或ID搜索学者信息

2. **步骤1_2**: 搜索学者并获取资料
   - 搜索学者并获取其完整资料

3. **步骤3**: 分析论文
   - 分析学者的论文数据

4. **步骤4_5**: 分析合著者和生成合著者网络
   - 分析学者的合著者信息
   - 生成合著者网络

5. **步骤6**: 计算学者评分
   - 根据论文和合著者数据计算学者评分

6. **步骤7**: 查找最常合作的合著者详情
   - 查找并获取最常合作的合著者的详细信息

7. **步骤8**: 生成批判性评价
   - 生成对学者的批判性评价

8. **步骤9**: 查找arxiv信息
   - 查找学者最被引用论文的arxiv信息

9. **步骤10**: 获取论文新闻
   - 获取学者最被引用论文的相关新闻

10. **步骤11**: 获取角色模型信息
    - 获取学者的角色模型信息

11. **步骤12**: 获取职业水平信息
    - 获取学者的职业水平信息

## 使用方法

### 测试单个学者

使用`test_single_scholar.py`脚本测试单个学者的完整流程：

```bash
python tests/scholar_tests/test_single_scholar.py --url "https://scholar.google.com/citations?user=mG4imMEAAAAJ"
```

或者使用名称或ID：

```bash
python tests/scholar_tests/test_single_scholar.py --name "Andrew Ng"
python tests/scholar_tests/test_single_scholar.py --id "mG4imMEAAAAJ"
```

### 测试单个学者的所有步骤

使用`test_all_steps_single_scholar.py`脚本测试单个学者的所有步骤：

```bash
python tests/scholar_tests/test_all_steps_single_scholar.py --url "https://scholar.google.com/citations?user=mG4imMEAAAAJ"
```

可以指定输出目录：

```bash
python tests/scholar_tests/test_all_steps_single_scholar.py --url "https://scholar.google.com/citations?user=mG4imMEAAAAJ" --output-dir "reports/tests/andrew_ng"
```

### 测试单个学者的特定步骤

使用`test_specific_step.py`脚本测试单个学者的特定步骤：

```bash
python tests/scholar_tests/test_specific_step.py --url "https://scholar.google.com/citations?user=mG4imMEAAAAJ" --step 3
```

对于需要输入文件的步骤，可以指定输入文件：

```bash
python tests/scholar_tests/test_specific_step.py --url "https://scholar.google.com/citations?user=mG4imMEAAAAJ" --step 3 --input-file "reports/tests/steps/scholar_mG4imMEAAAAJ_author_data.json"
```

### 批量测试特定步骤

使用`batch_run_step.py`脚本批量测试特定步骤：

```bash
python tests/scholar_tests/batch_run_step.py --test-file tests/scholar_tests/quick_test.txt --step 3
```

可以限制测试的学者数量：

```bash
python tests/scholar_tests/batch_run_step.py --test-file tests/scholar_tests/0416测试.txt --step 3 --max-scholars 5
```

### 批量测试学者

使用`batch_test_scholars.py`脚本批量测试学者：

```bash
# 完整测试
python tests/scholar_tests/batch_test_scholars.py --test-file tests/scholar_tests/quick_test.txt --test-type full

# 所有步骤测试
python tests/scholar_tests/batch_test_scholars.py --test-file tests/scholar_tests/quick_test.txt --test-type steps

# 特定步骤测试
python tests/scholar_tests/batch_test_scholars.py --test-file tests/scholar_tests/quick_test.txt --test-type specific_step --step 3
```

高级选项：

```bash
# 并行测试
python tests/scholar_tests/batch_test_scholars.py --test-file tests/scholar_tests/quick_test.txt --test-type full --parallel --max-workers 4

# 设置超时时间
python tests/scholar_tests/batch_test_scholars.py --test-file tests/scholar_tests/quick_test.txt --test-type full --timeout 600

# 从特定索引开始测试
python tests/scholar_tests/batch_test_scholars.py --test-file tests/scholar_tests/0416测试.txt --test-type full --start-index 5 --max-scholars 10
```

### 运行所有测试

使用`run_all_tests.sh`脚本一键运行所有测试：

```bash
./tests/scholar_tests/run_all_tests.sh
```

## 测试结果

所有测试结果都会保存在`reports/tests`目录下，按测试类型和步骤组织。每个测试都会生成详细的日志文件，记录测试过程中的输出和错误信息。

测试结果目录结构：

```
reports/tests/
├── full/                  # 完整测试结果
├── steps/                 # 所有步骤测试结果
├── step1/                 # 步骤1测试结果
├── step1_2/               # 步骤1_2测试结果
├── step3/                 # 步骤3测试结果
...
└── test_results.json      # 测试结果摘要
```

## 常见问题

### 1. 测试超时

如果测试超时，可以增加超时时间：

```bash
python tests/scholar_tests/batch_test_scholars.py --test-file tests/scholar_tests/quick_test.txt --test-type full --timeout 600
```

### 2. 需要输入文件的步骤

某些步骤（如步骤3、4_5等）需要前一步骤的输出作为输入。如果单独测试这些步骤，需要提供输入文件：

```bash
python tests/scholar_tests/test_specific_step.py --url "https://scholar.google.com/citations?user=mG4imMEAAAAJ" --step 3 --input-file "reports/tests/steps/scholar_mG4imMEAAAAJ_author_data.json"
```

### 3. 并行测试注意事项

并行测试可以提高测试效率，但也会增加系统负载。请根据系统配置调整并行度：

```bash
python tests/scholar_tests/batch_test_scholars.py --test-file tests/scholar_tests/quick_test.txt --test-type full --parallel --max-workers 4
```

### 4. API限制

某些步骤（如步骤7、8、9、10等）需要调用外部API，可能会受到API限制。如果遇到API限制，可以减少测试数量或增加测试间隔。

### 5. 测试文件格式

测试文件的格式为：`学者名称, Google Scholar URL`，每行一个学者。例如：

```
Andrew Ng, https://scholar.google.com/citations?user=mG4imMEAAAAJ&hl=en&oi=ao
Andrej Karpathy, https://scholar.google.com/citations?user=l8WuQJgAAAAJ&hl=en
```

---

如有任何问题或建议，请联系项目维护者。
