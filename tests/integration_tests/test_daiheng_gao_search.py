#!/usr/bin/env python
# coding: UTF-8
"""
专门测试 Daiheng Gao 的搜索案例
"""

import sys
import os
import time
from typing import Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from account.filter_scholar import filter_user_input
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.scholar_service import run_scholar_analysis

API_TOKEN = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""

def test_filter_user_input():
    """测试 filter_user_input 函数处理 Daiheng Gao 相关输入"""
    test_cases = [
        "Daiheng Gao",
        "Daiheng Gao,AI",
        "Daiheng Gao, AI",  # 添加空格
        "Daiheng Gao, Independent researcher",
        "Daiheng, Gao",  # 逗号位置不同
        "Y-ql3zMAAAAJ"
    ]
    
    print("\n测试 filter_user_input 函数:")
    for test_case in test_cases:
        result = filter_user_input(test_case)
        print(f"输入: '{test_case}' -> 输出: {result}")

def test_search_author():
    """测试 search_author_by_name 函数"""
    data_fetcher = ScholarDataFetcher(use_crawlbase=bool(API_TOKEN), api_token=API_TOKEN or None)
    
    test_cases = [
        "Daiheng Gao",
        "Daiheng Gao,AI",
        "Daiheng Gao, AI",  # 添加空格
        "Daiheng Gao, Independent researcher",
        "Daiheng, Gao"  # 逗号位置不同
    ]
    
    print("\n测试 search_author_by_name 函数:")
    for test_case in test_cases:
        print(f"\n搜索: '{test_case}'")
        authors = data_fetcher.search_author_by_name(test_case)
        
        if authors:
            print(f"找到 {len(authors)} 个匹配作者:")
            for i, author in enumerate(authors[:3], 1):  # 只显示前3个
                print(f"{i}. {author['name']} - {author['affiliation']} (ID: {author['scholar_id']})")
        else:
            print("未找到匹配作者")
        
        time.sleep(2)  # 暂停一下，避免请求过快

def test_run_scholar_analysis():
    """测试完整的 Scholar 分析流程"""
    test_cases = [
        {"name": "只用姓名", "input": "Daiheng Gao", "use_id": False},
        {"name": "姓名加领域", "input": "Daiheng Gao,AI", "use_id": False},
        {"name": "直接用ID", "input": "Y-ql3zMAAAAJ", "use_id": True}
    ]
    
    print("\n测试完整的 Scholar 分析流程:")
    for test_case in test_cases:
        print(f"\n测试: {test_case['name']} ('{test_case['input']}')")
        
        try:
            if test_case["use_id"]:
                # 使用 scholar_id
                report = run_scholar_analysis(
                    scholar_id=test_case["input"],
                    use_crawlbase=bool(API_TOKEN),
                    api_token=API_TOKEN or None,
                    use_cache=True,
                    cache_max_age_days=3
                )
            else:
                # 使用研究者姓名
                report = run_scholar_analysis(
                    researcher_name=test_case["input"],
                    use_crawlbase=bool(API_TOKEN),
                    api_token=API_TOKEN or None,
                    use_cache=True,
                    cache_max_age_days=3
                )
            
            if report:
                researcher = report.get("researcher", {})
                print(f"分析成功!")
                print(f"姓名: {researcher.get('name', 'N/A')}")
                print(f"机构: {researcher.get('affiliation', 'N/A')}")
                print(f"Scholar ID: {researcher.get('scholar_id', 'N/A')}")
                print(f"H指数: {researcher.get('h_index', 'N/A')}")
                print(f"总引用: {researcher.get('total_citations', 'N/A')}")
            else:
                print("分析失败: 未返回报告")
        
        except Exception as e:
            print(f"发生错误: {str(e)}")
        
        time.sleep(2)  # 暂停一下，避免请求过快

def main():
    """主函数"""
    print("\n=== Daiheng Gao 搜索测试 ===\n")
    
    # 测试 filter_user_input 函数
    test_filter_user_input()
    
    # 测试 search_author_by_name 函数
    test_search_author()
    
    # 测试完整的 Scholar 分析流程
    test_run_scholar_analysis()
    
    print("\n测试完成")

if __name__ == "__main__":
    main()
