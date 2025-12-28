#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试名字匹配算法

这个脚本测试改进后的名字匹配算法，特别是针对"GE Hinton"和"Geoffrey Hinton"这样的情况。
"""

import os
import sys
import logging

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 导入改进的名字匹配方法
from server.services.scholar.analyzer import ScholarAnalyzer

def test_name_matching():
    """测试名字匹配算法"""
    analyzer = ScholarAnalyzer()
    
    test_cases = [
        # 基本情况
        ("Geoffrey Hinton", "Geoffrey Hinton", True),
        ("Geoffrey Hinton", "Geoff Hinton", False),  # 这个可能需要更复杂的逻辑
        
        # 中间名变体
        ("Geoffrey Hinton", "Geoffrey E. Hinton", True),
        ("Geoffrey E. Hinton", "Geoffrey Hinton", True),
        
        # 首字母缩写
        ("Geoffrey Hinton", "G. Hinton", True),
        ("G. Hinton", "Geoffrey Hinton", True),
        
        # 多个首字母缩写
        ("Geoffrey E. Hinton", "G. E. Hinton", True),
        ("G. E. Hinton", "Geoffrey E. Hinton", True),
        
        # 没有点号的首字母缩写
        ("Geoffrey Hinton", "G Hinton", True),
        ("G Hinton", "Geoffrey Hinton", True),
        
        # 特殊情况: "GE Hinton"
        ("Geoffrey Hinton", "GE Hinton", True),
        ("GE Hinton", "Geoffrey Hinton", True),
        ("Geoffrey E. Hinton", "GE Hinton", True),
        ("GE Hinton", "Geoffrey E. Hinton", True),
        
        # 其他学者的例子
        ("Yann LeCun", "Y. LeCun", True),
        ("Y. LeCun", "Yann LeCun", True),
        ("Yann LeCun", "YA LeCun", True),
        ("YA LeCun", "Yann A. LeCun", True),
        
        # 不同的人
        ("Geoffrey Hinton", "Yann LeCun", False),
        ("Geoffrey Hinton", "Andrew Ng", False),
        ("GE Hinton", "GE Smith", False),
    ]
    
    print("测试名字匹配算法:")
    print("=" * 80)
    print(f"{'研究者姓名':<20} | {'合作者姓名':<20} | {'预期结果':<10} | {'实际结果':<10} | {'是否通过':<10}")
    print("-" * 80)
    
    passed = 0
    failed = 0
    
    for researcher_name, collaborator_name, expected in test_cases:
        actual = analyzer.is_same_person(researcher_name, collaborator_name)
        status = "✓" if actual == expected else "✗"
        
        if actual == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{researcher_name:<20} | {collaborator_name:<20} | {str(expected):<10} | {str(actual):<10} | {status:<10}")
    
    print("-" * 80)
    print(f"测试结果: 通过 {passed}/{len(test_cases)} 测试用例 ({passed/len(test_cases)*100:.1f}%)")
    
    if failed > 0:
        print(f"失败: {failed}/{len(test_cases)} 测试用例 ({failed/len(test_cases)*100:.1f}%)")
    else:
        print("所有测试用例都通过了!")

if __name__ == "__main__":
    test_name_matching()
