#!/usr/bin/env python
# coding: UTF-8
"""
测试 Scholar 搜索流程，展示不同输入的处理方式和搜索结果
"""

import sys
import os
import time
from typing import Tuple, Union, Dict, Any, List

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from account.filter_scholar import filter_user_input
from server.services.scholar.data_fetcher import ScholarDataFetcher

class ScholarSearchSimulator:
    """模拟 Scholar 搜索流程"""
    
    def __init__(self):
        """初始化"""
        api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
        self.data_fetcher = ScholarDataFetcher(use_crawlbase=bool(api_token), api_token=api_token or None)
    
    def search(self, user_input: str) -> Dict[str, Any]:
        """
        模拟搜索流程
        
        Args:
            user_input: 用户输入
            
        Returns:
            搜索结果
        """
        print(f"\n开始处理输入: '{user_input}'")
        
        # 步骤 1: 使用 filter_user_input 处理输入
        processed_input, is_name = filter_user_input(user_input)
        
        if is_name:
            print(f"输入被识别为研究者姓名: '{processed_input}'")
            # 步骤 2A: 如果是姓名，搜索作者
            print("搜索作者...")
            authors = self.data_fetcher.search_author_by_name(processed_input)
            
            if not authors:
                return {"success": False, "message": "未找到匹配的作者"}
            
            # 获取第一个匹配的作者
            author = authors[0]
            scholar_id = author["scholar_id"]
            print(f"找到作者: {author['name']} (ID: {scholar_id})")
            
        else:
            print(f"输入被识别为 Scholar ID: '{processed_input}'")
            # 步骤 2B: 如果是 ID，直接使用
            scholar_id = processed_input
        
        # 步骤 3: 获取作者详细信息
        print(f"获取作者详细信息 (ID: {scholar_id})...")
        author_details = self.data_fetcher.get_author_details_by_id(scholar_id)
        
        if not author_details:
            return {"success": False, "message": f"无法获取作者详细信息 (ID: {scholar_id})"}
        
        # 返回结果
        return {
            "success": True,
            "scholar_id": scholar_id,
            "author": author_details
        }

def run_test_cases():
    """运行测试用例"""
    # 初始化模拟器
    simulator = ScholarSearchSimulator()
    
    # 测试用例
    test_cases = [
        # Google Scholar ID
        "Y-ql3zMAAAAJ",
        
        # Google Scholar URL
        "https://scholar.google.com/citations?user=Y-ql3zMAAAAJ",
        
        # 只有姓名
        "Daiheng Gao",
        
        # 姓名加领域
        "Daiheng Gao,AI",
        
        # 姓名加机构
        "Ian Goodfellow,DeepMind"
    ]
    
    # 运行测试
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print("\n" + "=" * 80)
        print(f"测试 {i}: '{test_case}'")
        print("=" * 80)
        
        try:
            result = simulator.search(test_case)
            success = result.get("success", False)
            
            if success:
                author = result["author"]
                print(f"\n搜索成功!")
                print(f"作者: {author.get('full_name', 'N/A')}")
                print(f"机构: {author.get('affiliation', 'N/A')}")
                print(f"H指数: {author.get('h_index', 'N/A')}")
                print(f"总引用: {author.get('total_citations', 'N/A')}")
            else:
                print(f"\n搜索失败: {result.get('message', '未知错误')}")
            
            results.append({
                "input": test_case,
                "success": success,
                "result": result
            })
            
        except Exception as e:
            print(f"\n发生错误: {str(e)}")
            results.append({
                "input": test_case,
                "success": False,
                "error": str(e)
            })
        
        # 暂停一下，避免请求过快
        time.sleep(2)
    
    # 打印总结
    print("\n" + "=" * 80)
    print("测试结果总结")
    print("=" * 80)
    
    for i, result in enumerate(results, 1):
        success = "✓ 成功" if result["success"] else "✗ 失败"
        print(f"{i}. 输入: '{result['input']}' - {success}")

def main():
    """主函数"""
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
    run_test_cases()

if __name__ == "__main__":
    main()
