#!/bin/bash
# 运行所有学者服务测试的脚本

# 设置基本参数
TEST_FILE="tests/scholar_tests/quick_test.txt"
OUTPUT_DIR="reports/tests"
TIMEOUT=300

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 打印标题
echo "====================================================="
echo "           学者服务测试套件                          "
echo "====================================================="
echo

# 1. 运行完整测试
echo "1. 运行完整测试..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type full --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 2. 运行所有步骤测试
echo "2. 运行所有步骤测试..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type steps --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 3. 运行各个步骤的测试
echo "3. 运行各个步骤的测试..."

# 步骤1: 搜索学者
echo "   步骤1: 搜索学者..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 1 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤1_2: 搜索学者并获取资料
echo "   步骤1_2: 搜索学者并获取资料..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 1_2 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤3: 分析论文
echo "   步骤3: 分析论文..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 3 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤4_5: 分析合著者和生成合著者网络
echo "   步骤4_5: 分析合著者和生成合著者网络..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 4_5 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤6: 计算学者评分
echo "   步骤6: 计算学者评分..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 6 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤7: 查找最常合作的合著者详情
echo "   步骤7: 查找最常合作的合著者详情..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 7 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤8: 生成批判性评价
echo "   步骤8: 生成批判性评价..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 8 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤9: 查找arxiv信息
echo "   步骤9: 查找arxiv信息..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 9 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤10: 获取论文新闻
echo "   步骤10: 获取论文新闻..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 10 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤11: 获取角色模型信息
echo "   步骤11: 获取角色模型信息..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 11 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 步骤12: 获取职业水平信息
echo "   步骤12: 获取职业水平信息..."
python tests/scholar_tests/batch_test_scholars.py --test-file "$TEST_FILE" --test-type specific_step --step 12 --output-dir "$OUTPUT_DIR" --timeout "$TIMEOUT"
echo

# 打印测试完成信息
echo "====================================================="
echo "           学者服务测试完成                          "
echo "====================================================="
echo "测试结果保存在: $OUTPUT_DIR"
echo
