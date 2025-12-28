#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证stream_processor中的数据库缓存功能

此脚本测试stream_processor中的数据库缓存功能，包括：
1. 提取学者ID
2. 将学者ID添加到reportData
3. 保存数据到缓存
4. 从缓存获取数据
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入数据库相关模块
try:
    from src.utils.db_utils import create_tables
    from src.utils.scholar_cache import get_cached_scholar, cache_scholar_data
    from server.api.scholar.db_cache import get_scholar_from_cache, save_scholar_to_cache
    
    # 确保数据库表已创建
    create_tables()
    
    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def test_extract_scholar_id():
    """测试从scholar_data中提取学者ID"""
    print("\n=== 测试从scholar_data中提取学者ID ===")
    
    # 创建测试数据
    scholar_data = {
        "researcher": {
            "name": "Test Researcher",
            "affiliation": "Test University",
            "scholar_id": "TEST123456"
        }
    }
    
    # 提取学者ID
    scholar_id = None
    if scholar_data and "researcher" in scholar_data:
        if "scholar_id" in scholar_data["researcher"]:
            scholar_id = scholar_data["researcher"]["scholar_id"]
    
    if scholar_id == "TEST123456":
        print(f"✅ 成功提取学者ID: {scholar_id}")
        return True
    else:
        print(f"❌ 提取学者ID失败")
        return False

def test_add_scholar_id_to_report_urls():
    """测试将学者ID添加到report_urls"""
    print("\n=== 测试将学者ID添加到report_urls ===")
    
    # 创建测试数据
    report_urls = {
        "json_url": "http://example.com/report.json",
        "html_url": "http://example.com/report.html",
        "researcher_name": "Test Researcher"
    }
    
    # 添加学者ID
    scholar_id = "TEST123456"
    report_urls["scholar_id"] = scholar_id
    
    if "scholar_id" in report_urls and report_urls["scholar_id"] == scholar_id:
        print(f"✅ 成功将学者ID添加到report_urls: {report_urls['scholar_id']}")
        return True
    else:
        print(f"❌ 将学者ID添加到report_urls失败")
        return False

def test_create_report_data_message():
    """测试创建包含学者ID的reportData消息"""
    print("\n=== 测试创建包含学者ID的reportData消息 ===")
    
    # 导入create_report_data_message函数
    from server.api.scholar.utils import create_report_data_message
    
    # 创建测试数据
    report_urls = {
        "json_url": "http://example.com/report.json",
        "html_url": "http://example.com/report.html",
        "researcher_name": "Test Researcher",
        "scholar_id": "TEST123456"
    }
    
    # 创建reportData消息
    message = create_report_data_message(report_urls)
    
    if (message["type"] == "reportData" and 
        "scholarId" in message["content"] and 
        message["content"]["scholarId"] == "TEST123456"):
        print(f"✅ 成功创建包含学者ID的reportData消息")
        print(f"   scholarId: {message['content']['scholarId']}")
        return True
    else:
        print(f"❌ 创建包含学者ID的reportData消息失败")
        return False

def test_completion_data_with_scholar_id():
    """测试创建包含学者ID的completion_data"""
    print("\n=== 测试创建包含学者ID的completion_data ===")
    
    # 创建测试数据
    report_urls = {
        "json_url": "http://example.com/report.json",
        "html_url": "http://example.com/report.html",
        "researcher_name": "Test Researcher",
        "scholar_id": "TEST123456"
    }
    
    # 创建report_data
    report_data = {
        "jsonUrl": report_urls["json_url"],
        "htmlUrl": report_urls["html_url"],
        "researcherName": report_urls["researcher_name"]
    }
    
    # 如果有学者ID，添加到reportData中
    if "scholar_id" in report_urls:
        report_data["scholarId"] = report_urls["scholar_id"]
    
    # 创建completion_data
    completion_data = {
        "type": "completion",
        "content": "Analysis Complete",
        "state": "completed",
        "timestamp": time.time(),
        "reportData": report_data
    }
    
    if ("reportData" in completion_data and 
        "scholarId" in completion_data["reportData"] and 
        completion_data["reportData"]["scholarId"] == "TEST123456"):
        print(f"✅ 成功创建包含学者ID的completion_data")
        print(f"   scholarId: {completion_data['reportData']['scholarId']}")
        return True
    else:
        print(f"❌ 创建包含学者ID的completion_data失败")
        return False

def test_save_and_get_from_cache():
    """测试保存数据到缓存并从缓存获取数据"""
    if not DB_AVAILABLE:
        print("\n数据库模块不可用，跳过测试")
        return False
    
    print("\n=== 测试保存数据到缓存并从缓存获取数据 ===")
    
    # 创建测试数据
    scholar_id = "TEST123456"
    scholar_data = {
        "researcher": {
            "name": "Test Researcher",
            "affiliation": "Test University",
            "scholar_id": scholar_id,
            "h_index": 20,
            "total_citations": 1000
        },
        "publication_stats": {
            "total_papers": 50,
            "first_author_papers": 20
        }
    }
    
    # 保存数据到缓存
    print("\n1. 保存数据到缓存...")
    success = save_scholar_to_cache(scholar_data, scholar_id)
    if success:
        print(f"✅ 成功将学者 {scholar_id} 的数据保存到缓存")
    else:
        print(f"❌ 保存学者 {scholar_id} 的数据到缓存失败")
        return False
    
    # 从缓存获取数据
    print("\n2. 从缓存获取数据...")
    cached_data = get_scholar_from_cache(scholar_id)
    if cached_data:
        print(f"✅ 从缓存成功获取到学者 {scholar_id} 的数据")
        
        # 验证数据
        if (cached_data["researcher"]["name"] == "Test Researcher" and
            cached_data["researcher"]["h_index"] == 20 and
            cached_data["publication_stats"]["total_papers"] == 50):
            print(f"✅ 缓存数据验证成功")
            return True
        else:
            print(f"❌ 缓存数据验证失败")
            return False
    else:
        print(f"❌ 从缓存获取学者 {scholar_id} 的数据失败")
        return False

def run_all_tests():
    """运行所有测试"""
    print("=== 开始测试stream_processor中的数据库缓存功能 ===")
    
    tests = [
        test_extract_scholar_id,
        test_add_scholar_id_to_report_urls,
        test_create_report_data_message,
        test_completion_data_with_scholar_id,
        test_save_and_get_from_cache
    ]
    
    success_count = 0
    for test in tests:
        if test():
            success_count += 1
    
    print(f"\n=== 测试完成: {success_count}/{len(tests)} 个测试通过 ===")
    return success_count == len(tests)

if __name__ == "__main__":
    run_all_tests()
