#!/usr/bin/env python
# coding: UTF-8
"""
测试报告生成器的文件命名方式
"""

import sys
import os
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from server.api.scholar.report_generator import save_scholar_report

def test_report_generator():
    """测试报告生成器的文件命名方式"""
    # 创建一个测试报告
    test_report = {
        "researcher": {
            "name": "Test Researcher",
            "scholar_id": "TEST123456",
            "affiliation": "Test University",
            "h_index": 10,
            "total_citations": 1000
        },
        "publication_stats": {
            "total_papers": 50,
            "first_author_papers": 20
        }
    }
    
    # 保存报告
    result = save_scholar_report(test_report, "Test Query", "test-session-id")
    
    # 打印结果
    print("\n保存报告结果:")
    print(f"JSON URL: {result['json_url']}")
    print(f"HTML URL: {result['html_url']}")
    print(f"研究者名称: {result['researcher_name']}")
    
    # 检查文件是否存在
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    json_filename = f"Test_Researcher_TEST123456.json"
    json_filepath = os.path.join(reports_dir, json_filename)
    
    formatted_json_filename = f"Test_Researcher_TEST123456_formatted.json"
    formatted_json_filepath = os.path.join(reports_dir, formatted_json_filename)
    
    print("\n文件检查:")
    print(f"原始 JSON 文件存在: {os.path.exists(json_filepath)}")
    print(f"格式化 JSON 文件存在: {os.path.exists(formatted_json_filepath)}")
    
    # 测试没有 Scholar ID 的情况
    test_report_no_id = {
        "researcher": {
            "name": "No ID Researcher",
            "affiliation": "Test University",
            "h_index": 5,
            "total_citations": 500
        }
    }
    
    # 保存报告
    result_no_id = save_scholar_report(test_report_no_id, "No ID Query", "no-id-session")
    
    # 打印结果
    print("\n没有 Scholar ID 的保存结果:")
    print(f"JSON URL: {result_no_id['json_url']}")
    print(f"HTML URL: {result_no_id['html_url']}")
    print(f"研究者名称: {result_no_id['researcher_name']}")

def main():
    """主函数"""
    print("\n=== 测试报告生成器 ===\n")
    
    # 运行测试
    test_report_generator()
    
    print("\n测试完成")

if __name__ == "__main__":
    main()
