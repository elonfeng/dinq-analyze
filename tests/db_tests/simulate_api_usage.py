#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模拟API使用场景

此脚本模拟多个用户调用API的场景，并记录API使用情况。
"""

import os
import sys
import time
import random
from datetime import datetime, timedelta

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

# 模拟用户列表
USERS = [
    "ffQNKT7sMMQ0MBxpFOQFMcAk3k72",  # 真实用户
    "user123",                        # 模拟用户
    "user456",                        # 模拟用户
    "admin789"                        # 模拟用户
]

# 模拟端点列表
ENDPOINTS = [
    "/api/stream",
    "/api/scholar-pk"
]

# 模拟查询列表
QUERIES = [
    "John Smith",
    "Albert Einstein",
    "Marie Curie",
    "Isaac Newton",
    "Nikola Tesla",
    "Stephen Hawking",
    "Ada Lovelace",
    "Alan Turing"
]

def simulate_api_calls(num_calls=20, days_back=7):
    """模拟多个API调用并记录到数据库"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过测试")
        return
    
    print(f"\n模拟 {num_calls} 次API调用...")
    
    # 获取当前时间
    now = datetime.now()
    
    # 模拟API调用
    for i in range(num_calls):
        # 随机选择用户、端点和查询
        user_id = random.choice(USERS)
        endpoint = random.choice(ENDPOINTS)
        query = random.choice(QUERIES)
        
        # 随机生成时间（过去几天内）
        random_days = random.uniform(0, days_back)
        random_hours = random.uniform(0, 24)
        random_time = now - timedelta(days=random_days, hours=random_hours)
        
        # 随机生成执行时间（1-10秒）
        execution_time = random.uniform(1, 10)
        
        # 随机生成状态（90%成功，10%失败）
        status = "success" if random.random() < 0.9 else "error"
        error_message = "模拟错误" if status == "error" else None
        
        # 创建API使用记录
        try:
            with get_db_session() as session:
                api_usage = ApiUsage(
                    user_id=user_id,
                    endpoint=endpoint,
                    query=query,
                    query_type="scholar_name",
                    scholar_id=None,
                    status=status,
                    error_message=error_message,
                    execution_time=execution_time,
                    ip_address="192.168.1." + str(random.randint(1, 255)),
                    user_agent="Mozilla/5.0 (Simulation)",
                    created_at=random_time
                )
                session.add(api_usage)
                print(f"添加记录 {i+1}/{num_calls}: 用户={user_id}, 端点={endpoint}, 查询={query}, 时间={random_time}")
        except Exception as e:
            print(f"添加记录失败: {e}")
    
    print("\n模拟完成！")

def analyze_user_usage(user_id):
    """分析特定用户的API使用情况"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过分析")
        return
    
    print(f"\n分析用户 {user_id} 的API使用情况...")
    
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
            
            # 查询用户每天的API使用记录
            from sqlalchemy import func, cast, Date
            daily_counts = session.query(
                cast(ApiUsage.created_at, Date).label('date'),
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.user_id == user_id
            ).group_by('date').order_by('date').all()
            
            print("用户每天的API调用次数:")
            for date, count in daily_counts:
                print(f"  - {date}: {count}次")
            
            # 查询用户最近的API使用记录
            recent_calls = session.query(ApiUsage).filter(
                ApiUsage.user_id == user_id
            ).order_by(ApiUsage.created_at.desc()).limit(5).all()
            
            print(f"用户最近的API调用 (最多5条):")
            for i, call in enumerate(recent_calls, 1):
                print(f"  {i}. 端点: {call.endpoint}, 查询: {call.query}, 时间: {call.created_at}")
    except Exception as e:
        print(f"分析用户API使用情况失败: {e}")

if __name__ == "__main__":
    # 指定要测试的用户ID
    USER_ID = "ffQNKT7sMMQ0MBxpFOQFMcAk3k72"
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--simulate":
            # 模拟API调用
            num_calls = 20
            if len(sys.argv) > 2:
                num_calls = int(sys.argv[2])
            simulate_api_calls(num_calls)
        else:
            USER_ID = sys.argv[1]
    
    # 分析用户API使用情况
    analyze_user_usage(USER_ID)
