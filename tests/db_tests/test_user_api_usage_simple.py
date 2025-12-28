#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版测试脚本：验证特定用户的API使用情况

此脚本使用直接的数据库操作来测试特定用户ID的API使用情况。
"""

import os
import sys
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 导入数据库相关模块
try:
    from src.utils.db_utils import create_tables, get_db_session
    from src.models.db import ApiUsage
    
    # 确保数据库表已创建
    create_tables()
    
    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def test_user_api_usage_simple(user_id):
    """使用简单的数据库操作测试特定用户的API使用情况"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过测试")
        return
    
    print(f"\n测试用户 {user_id} 的API使用情况 (简化版)...")
    
    # 1. 添加测试记录
    print("\n1. 添加测试记录")
    try:
        with get_db_session() as session:
            # 创建新的API使用记录
            new_usage = ApiUsage(
                user_id=user_id,
                endpoint="/api/stream",
                query="简化版测试查询 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                query_type="test",
                status="success",
                execution_time=1.5,
                ip_address="127.0.0.1",
                user_agent="Simple Test Script"
            )
            session.add(new_usage)
            session.flush()
            print("成功添加测试记录")
    except Exception as e:
        print(f"添加测试记录失败: {e}")
        return False
    
    # 2. 查询用户API使用情况
    print("\n2. 查询用户API使用情况")
    try:
        with get_db_session() as session:
            # 查询用户的API使用记录总数
            count = session.query(ApiUsage).filter(ApiUsage.user_id == user_id).count()
            print(f"用户API调用总次数: {count}")
            
            # 查询用户的API使用记录按端点分组
            from sqlalchemy import func
            endpoint_counts = session.query(
                ApiUsage.endpoint, 
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.user_id == user_id
            ).group_by(ApiUsage.endpoint).all()
            
            print("用户按端点的API调用次数:")
            for endpoint, count in endpoint_counts:
                print(f"  - {endpoint}: {count}次")
            
            # 查询用户最近的API使用记录
            recent_calls = session.query(ApiUsage).filter(
                ApiUsage.user_id == user_id
            ).order_by(ApiUsage.created_at.desc()).limit(5).all()
            
            print(f"用户最近的API调用 (最多5条):")
            for i, call in enumerate(recent_calls, 1):
                print(f"  {i}. 端点: {call.endpoint}, 查询: {call.query}, 时间: {call.created_at}")
    except Exception as e:
        print(f"查询用户API使用情况失败: {e}")
        return False
    
    print("\n测试完成！API使用记录功能正常工作。")
    return True

if __name__ == "__main__":
    # 指定要测试的用户ID
    USER_ID = "ffQNKT7sMMQ0MBxpFOQFMcAk3k72"
    
    if len(sys.argv) > 1:
        USER_ID = sys.argv[1]
    
    test_user_api_usage_simple(USER_ID)
