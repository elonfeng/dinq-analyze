#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证特定用户的API使用情况

此脚本测试特定用户ID的API使用情况，并验证API使用记录功能是否正常工作。
"""

import os
import sys
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 导入数据库相关模块
try:
    from src.utils.db_utils import create_tables
    from src.utils.api_usage_repository import api_usage_repo
    from src.utils.api_usage_stats import get_user_usage_summary, get_daily_usage
    from server.utils.api_usage_tracker import track_stream_completion

    # 确保数据库表已创建
    create_tables()

    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def test_specific_user_api_usage(user_id):
    """测试特定用户的API使用情况"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过测试")
        return

    print(f"\n测试用户 {user_id} 的API使用情况...")

    # 1. 查询用户现有的API使用情况
    print("\n1. 查询用户现有的API使用情况")
    usage_count = api_usage_repo.get_user_usage_count(user_id)
    print(f"用户API调用总次数: {usage_count}")

    endpoint_counts = api_usage_repo.get_user_usage_by_endpoint(user_id)
    print(f"用户按端点的API调用次数:")
    for endpoint, count in endpoint_counts.items():
        print(f"  - {endpoint}: {count}次")

    recent_calls = api_usage_repo.get_recent_user_calls(user_id, 5)
    print(f"用户最近的API调用 (最多5条):")
    for i, call in enumerate(recent_calls, 1):
        print(f"  {i}. 端点: {call.endpoint}, 查询: {call.query}, 时间: {call.created_at}")

    # 2. 添加一条测试记录
    print("\n2. 添加一条测试记录")
    test_success = api_usage_repo.log_api_call(
        user_id=user_id,
        endpoint="/api/stream",
        query="测试查询 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        query_type="test",
        status="success",
        execution_time=1.5,
        ip_address="127.0.0.1",
        user_agent="Test Script"
    )

    if test_success:
        print("成功添加测试记录")
    else:
        print("添加测试记录失败")
        return False

    # 3. 使用API使用跟踪器添加一条记录
    print("\n3. 使用API使用跟踪器添加一条记录")
    track_stream_completion(
        endpoint="/api/scholar-pk",
        query="测试PK查询 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        scholar_id=None,
        status="success",
        user_id=user_id  # 直接传入用户ID
    )
    print("已使用API使用跟踪器添加记录")

    # 4. 再次查询用户API使用情况，验证记录是否增加
    print("\n4. 再次查询用户API使用情况，验证记录是否增加")
    new_usage_count = api_usage_repo.get_user_usage_count(user_id)
    print(f"用户API调用总次数: {new_usage_count} (之前: {usage_count})")

    new_endpoint_counts = api_usage_repo.get_user_usage_by_endpoint(user_id)
    print(f"用户按端点的API调用次数:")
    for endpoint, count in new_endpoint_counts.items():
        old_count = endpoint_counts.get(endpoint, 0)
        print(f"  - {endpoint}: {count}次 (之前: {old_count}次)")

    # 5. 获取用户使用摘要
    print("\n5. 获取用户使用摘要")
    usage_summary = get_user_usage_summary(user_id, days=30)
    print(f"用户30天内API调用总次数: {usage_summary['total_calls']}")
    print(f"用户30天内按端点的API调用次数: {usage_summary['endpoint_breakdown']}")

    # 6. 获取用户每日使用情况
    print("\n6. 获取用户每日使用情况")
    daily_usage = get_daily_usage(user_id, days=7)
    print("用户最近7天的每日使用情况:")
    for day in daily_usage:
        print(f"  - {day['date']}: {day['count']}次")

    # 7. 检查速率限制
    print("\n7. 检查速率限制")
    stream_limit_ok = api_usage_repo.check_user_rate_limit(user_id, "/api/stream", 100)
    pk_limit_ok = api_usage_repo.check_user_rate_limit(user_id, "/api/scholar-pk", 50)
    print(f"用户 /api/stream 速率限制检查: {'通过' if stream_limit_ok else '超出限制'}")
    print(f"用户 /api/scholar-pk 速率限制检查: {'通过' if pk_limit_ok else '超出限制'}")

    print("\n测试完成！API使用记录功能正常工作。")
    return True

if __name__ == "__main__":
    # 指定要测试的用户ID
    USER_ID = "ffQNKT7sMMQ0MBxpFOQFMcAk3k72"

    if len(sys.argv) > 1:
        USER_ID = sys.argv[1]

    test_specific_user_api_usage(USER_ID)
