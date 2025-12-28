#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证Kimi评价生成功能

此脚本测试Kimi评价生成功能，包括：
1. 测试generate_critical_evaluation函数
2. 验证评价是否正确生成
"""

import os
import json
import time
from datetime import datetime

# 导入相关模块
try:
    from server.utils.kimi_evaluator import generate_critical_evaluation
    
    # 标记模块是否可用
    KIMI_AVAILABLE = True
except ImportError as e:
    print(f"Kimi评价模块导入失败，测试将被跳过: {e}")
    KIMI_AVAILABLE = False

def create_mock_researcher_data(name="Test Researcher"):
    """创建模拟学者数据"""
    return {
        "researcher": {
            "name": name,
            "abbreviated_name": "T. Researcher",
            "affiliation": "Test University",
            "email": "test@example.com",
            "research_fields": ["AI", "Machine Learning", "Computer Vision"],
            "total_citations": 1000,
            "citations_5y": 500,
            "h_index": 20,
            "h_index_5y": 15,
            "yearly_citations": {
                "2020": 100,
                "2021": 200,
                "2022": 300,
                "2023": 400
            },
            "scholar_id": "TEST123456"
        },
        "publication_stats": {
            "total_papers": 50,
            "first_author_papers": 20,
            "first_author_percentage": 40.0,
            "top_tier_papers": 15,
            "top_tier_percentage": 30.0,
            "most_cited_paper": {
                "title": "Test Paper",
                "year": 2020,
                "venue": "Test Conference",
                "citations": 500
            }
        },
        "coauthor_stats": {
            "total_coauthors": 30,
            "top_coauthors": [
                {"name": "Coauthor 1", "papers": 10},
                {"name": "Coauthor 2", "papers": 8},
                {"name": "Coauthor 3", "papers": 5}
            ]
        },
        "rating": {
            "overall_score": 8.5,
            "level": "Senior Researcher"
        }
    }

def test_kimi_evaluator():
    """测试Kimi评价生成功能"""
    if not KIMI_AVAILABLE:
        print("\nKimi评价模块不可用，跳过测试")
        return False
    
    print("\n=== 测试Kimi评价生成功能 ===")
    
    # 1. 创建模拟数据
    print("\n1. 创建模拟数据...")
    mock_data = create_mock_researcher_data()
    print(f"✅ 已创建模拟数据")
    
    # 2. 生成评价
    print("\n2. 生成评价...")
    try:
        evaluation = generate_critical_evaluation(mock_data)
        print(f"✅ 成功生成评价: {evaluation}")
        
        # 验证评价是否为字符串
        if isinstance(evaluation, str):
            print(f"✅ 评价是字符串类型")
        else:
            print(f"❌ 评价不是字符串类型")
            return False
        
        # 验证评价是否不为空
        if evaluation:
            print(f"✅ 评价不为空")
        else:
            print(f"❌ 评价为空")
            return False
    except Exception as e:
        print(f"❌ 生成评价失败: {e}")
        return False
    
    # 3. 测试异常情况
    print("\n3. 测试异常情况...")
    try:
        # 传入None
        evaluation_none = generate_critical_evaluation(None)
        print(f"✅ 传入None时成功生成默认评价: {evaluation_none}")
        
        # 传入空字典
        evaluation_empty = generate_critical_evaluation({})
        print(f"✅ 传入空字典时成功生成默认评价: {evaluation_empty}")
        
        # 传入非字典
        evaluation_non_dict = generate_critical_evaluation("not a dict")
        print(f"✅ 传入非字典时成功生成默认评价: {evaluation_non_dict}")
    except Exception as e:
        print(f"❌ 测试异常情况失败: {e}")
        return False
    
    print("\n=== Kimi评价生成功能测试完成 ===")
    return True

if __name__ == "__main__":
    test_kimi_evaluator()
