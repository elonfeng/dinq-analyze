#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证学者ID是否正确添加到报告中

此脚本测试学者ID是否正确添加到报告中，包括：
1. 从ScholarService.generate_report获取报告
2. 检查报告中是否包含学者ID
3. 从run_scholar_analysis获取报告
4. 检查报告中是否包含学者ID
"""

import os
import json
import time
from datetime import datetime

# 导入相关模块
from server.services.scholar.scholar_service import ScholarService, run_scholar_analysis

def test_scholar_id_in_generate_report(scholar_id="ZUeyIxMAAAAJ"):
    """测试ScholarService.generate_report是否正确添加学者ID"""
    print(f"\n=== 测试ScholarService.generate_report是否正确添加学者ID ===")
    print(f"学者ID: {scholar_id}")
    
    # 初始化ScholarService
    api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
    scholar_service = ScholarService(use_crawlbase=bool(api_token), api_token=api_token or None)
    
    # 生成报告
    print("\n1. 生成报告...")
    report = scholar_service.generate_report(scholar_id=scholar_id)
    
    # 检查报告中是否包含学者ID
    print("\n2. 检查报告中是否包含学者ID...")
    if report and 'researcher' in report and 'scholar_id' in report['researcher']:
        scholar_id_in_report = report['researcher']['scholar_id']
        print(f"✅ 报告中包含学者ID: {scholar_id_in_report}")
        
        # 检查学者ID是否正确
        if scholar_id_in_report == scholar_id:
            print(f"✅ 学者ID正确")
        else:
            print(f"❌ 学者ID不正确，期望: {scholar_id}，实际: {scholar_id_in_report}")
    else:
        print(f"❌ 报告中不包含学者ID")
        return False
    
    return True

def test_scholar_id_in_run_scholar_analysis(scholar_id="ZUeyIxMAAAAJ"):
    """测试run_scholar_analysis是否正确添加学者ID"""
    print(f"\n=== 测试run_scholar_analysis是否正确添加学者ID ===")
    print(f"学者ID: {scholar_id}")

    api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""

    # 定义回调函数
    logs = []
    def callback(message):
        logs.append(message)
    
    # 运行分析
    print("\n1. 运行分析...")
    report = run_scholar_analysis(
        scholar_id=scholar_id, 
        use_crawlbase=bool(api_token),
        api_token=api_token or None,
        callback=callback
    )
    
    # 检查报告中是否包含学者ID
    print("\n2. 检查报告中是否包含学者ID...")
    if report and 'researcher' in report and 'scholar_id' in report['researcher']:
        scholar_id_in_report = report['researcher']['scholar_id']
        print(f"✅ 报告中包含学者ID: {scholar_id_in_report}")
        
        # 检查学者ID是否正确
        if scholar_id_in_report == scholar_id:
            print(f"✅ 学者ID正确")
        else:
            print(f"❌ 学者ID不正确，期望: {scholar_id}，实际: {scholar_id_in_report}")
    else:
        print(f"❌ 报告中不包含学者ID")
        return False
    
    # 检查日志中是否包含学者ID相关信息
    print("\n3. 检查日志中是否包含学者ID相关信息...")
    scholar_id_logs = [log for log in logs if "scholar_id" in log or "ID:" in log]
    if scholar_id_logs:
        print(f"✅ 日志中包含学者ID相关信息:")
        for log in scholar_id_logs:
            print(f"   - {log}")
    else:
        print(f"❌ 日志中不包含学者ID相关信息")
    
    return True

def run_all_tests():
    """运行所有测试"""
    print("=== 开始测试学者ID是否正确添加到报告中 ===")
    
    # 测试ScholarService.generate_report
    test1 = test_scholar_id_in_generate_report()
    
    # 测试run_scholar_analysis
    test2 = test_scholar_id_in_run_scholar_analysis()
    
    # 总结
    print(f"\n=== 测试结果 ===")
    print(f"ScholarService.generate_report: {'通过' if test1 else '失败'}")
    print(f"run_scholar_analysis: {'通过' if test2 else '失败'}")
    
    return test1 and test2

if __name__ == "__main__":
    run_all_tests()
