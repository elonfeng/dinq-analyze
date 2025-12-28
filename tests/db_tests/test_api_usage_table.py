#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证 ApiUsage 表是否正确创建

此脚本测试 ApiUsage 表是否正确创建，并测试基本的 CRUD 操作。
"""

import os
import sys
import json
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 导入数据库相关模块
try:
    from src.utils.db_utils import create_tables
    from src.models.db import ApiUsage
    from src.utils.api_usage_repository import api_usage_repo

    # 确保数据库表已创建
    create_tables()

    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def test_api_usage_table():
    """测试 ApiUsage 表是否正确创建"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过测试")
        return

    print("\n测试 ApiUsage 表...")

    # 创建测试记录
    test_data = {
        "user_id": "test_user_123",
        "endpoint": "/api/stream",
        "query": "Test Scholar Query",
        "query_type": "scholar_name",
        "scholar_id": "ABC123",
        "status": "success",
        "execution_time": 2.5,
        "ip_address": "127.0.0.1",
        "user_agent": "Test Agent"
    }

    # 记录API调用
    success = api_usage_repo.log_api_call(**test_data)

    if success:
        print("成功创建API使用记录")

        # 获取用户使用统计
        usage_count = api_usage_repo.get_user_usage_count("test_user_123")
        print(f"用户API调用次数: {usage_count}")

        # 获取用户按端点的使用统计
        endpoint_counts = api_usage_repo.get_user_usage_by_endpoint("test_user_123")
        print(f"用户按端点的API调用次数: {endpoint_counts}")

        # 获取用户最近的调用
        recent_calls = api_usage_repo.get_recent_user_calls("test_user_123")
        print(f"用户最近的API调用: {len(recent_calls)} 条记录")

        # 检查速率限制
        rate_limit_ok = api_usage_repo.check_user_rate_limit("test_user_123", "/api/stream", 10)
        print(f"用户速率限制检查: {'通过' if rate_limit_ok else '超出限制'}")

        print("ApiUsage 表测试成功!")
        return True
    else:
        print("创建API使用记录失败")
        return False

if __name__ == "__main__":
    test_api_usage_table()
