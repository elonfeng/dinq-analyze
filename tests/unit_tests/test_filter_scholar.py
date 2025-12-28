#!/usr/bin/env python
# coding: UTF-8
"""
测试 filter_user_input 函数的各种输入情况
"""

from account.filter_scholar import filter_user_input

def test_filter_user_input():
    """
    测试不同类型的输入如何被 filter_user_input 函数处理
    """
    # 测试用例列表：(输入, 预期输出, 描述)
    test_cases = [
        # Google Scholar URL
        (
            "https://scholar.google.com/citations?user=Y-ql3zMAAAAJ&hl=en", 
            ("Y-ql3zMAAAAJ", False),
            "完整的Google Scholar URL (带额外参数)"
        ),
        (
            "https://scholar.google.com/citations?user=Y-ql3zMAAAAJ", 
            ("Y-ql3zMAAAAJ", False),
            "完整的Google Scholar URL (无额外参数)"
        ),
        
        # Google Scholar ID
        (
            "Y-ql3zMAAAAJ", 
            ("Y-ql3zMAAAAJ", False),
            "直接输入Google Scholar ID"
        ),
        (
            "iYN86KEAAAAJ", 
            ("iYN86KEAAAAJ", False),
            "另一个Google Scholar ID (Ian Goodfellow)"
        ),
        
        # 研究者姓名 (无机构)
        (
            "Daiheng Gao", 
            ("Daiheng Gao", True),
            "只有姓名，无机构信息"
        ),
        (
            "Ian Goodfellow", 
            ("Ian Goodfellow", True),
            "只有姓名，无机构信息"
        ),
        
        # 研究者姓名 (带机构)
        (
            "Daiheng Gao,AI", 
            ("Daiheng Gao,AI", True),
            "姓名加领域信息"
        ),
        (
            "Ian Goodfellow,DeepMind", 
            ("Ian Goodfellow,DeepMind", True),
            "姓名加机构信息"
        ),
        (
            "Yann LeCun,Facebook AI Research", 
            ("Yann LeCun,Facebook AI Research", True),
            "姓名加完整机构名称"
        ),
        
        # 特殊情况
        (
            "scholar.google.com/citations?user=Y-ql3zMAAAAJ", 
            ("scholar.google.com/citations?user=Y-ql3zMAAAAJ", True),
            "不完整的URL (缺少https://)"
        ),
        (
            "Y-ql3zM", 
            ("Y-ql3zM", True),
            "不完整的Scholar ID"
        ),
    ]
    
    # 运行测试用例
    print("=" * 80)
    print("测试 filter_user_input 函数")
    print("=" * 80)
    
    for i, (input_str, expected_output, description) in enumerate(test_cases, 1):
        result = filter_user_input(input_str)
        
        # 检查结果是否符合预期
        is_correct = result == expected_output
        
        # 打印测试结果
        print(f"\n测试 {i}: {description}")
        print(f"输入: '{input_str}'")
        print(f"预期输出: {expected_output}")
        print(f"实际输出: {result}")
        print(f"结果: {'✓ 通过' if is_correct else '✗ 失败'}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

def main():
    """
    主函数
    """
    print("\n用户指南: 如何使用 Scholar 搜索功能\n")
    print("您可以通过以下三种方式输入查询:")
    print("1. Google Scholar URL: https://scholar.google.com/citations?user=Y-ql3zMAAAAJ")
    print("2. Google Scholar ID: Y-ql3zMAAAAJ")
    print("3. 研究者姓名和机构: Daiheng Gao,AI")
    print("\n注意事项:")
    print("- 当输入仅包含姓名时 (如 'Daiheng Gao')，系统可能难以准确找到目标研究者")
    print("- 建议在姓名后添加逗号和机构/领域信息 (如 'Daiheng Gao,AI')")
    print("- 直接使用Google Scholar URL或ID可以获得最准确的结果")
    print("\n现在运行测试...\n")
    
    # 运行测试
    test_filter_user_input()

if __name__ == "__main__":
    main()
