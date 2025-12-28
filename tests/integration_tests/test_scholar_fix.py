#!/usr/bin/env python
# coding: UTF-8
"""
测试修复后的 Scholar 搜索功能
"""

import sys
import os
import time

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.scholar_service import run_scholar_analysis

API_TOKEN = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""

def test_search_researcher():
    """测试 search_researcher 方法"""
    data_fetcher = ScholarDataFetcher(use_crawlbase=bool(API_TOKEN), api_token=API_TOKEN or None)
    
    # 测试用例
    test_cases = [
        {"name": "只用姓名", "input": "Daiheng Gao", "use_id": False},
        {"name": "姓名加领域", "input": "Daiheng Gao,AI", "use_id": False},
        {"name": "直接用ID", "input": "Y-ql3zMAAAAJ", "use_id": True}
    ]
    
    for test_case in test_cases:
        print(f"\n测试: {test_case['name']} ('{test_case['input']}')")
        
        if test_case["use_id"]:
            # 使用 scholar_id
            result = data_fetcher.search_researcher(scholar_id=test_case["input"])
        else:
            # 使用研究者姓名
            result = data_fetcher.search_researcher(name=test_case["input"])
        
        if result:
            print(f"搜索成功: {result}")
        else:
            print(f"搜索失败")
        
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
    print("\n=== Scholar 搜索修复测试 ===\n")
    
    # 测试 search_researcher 方法
    test_search_researcher()
    
    # 测试完整的 Scholar 分析流程
    test_run_scholar_analysis()
    
    print("\n测试完成")

if __name__ == "__main__":
    main()
