#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API使用管理工具

此脚本提供了查询和管理API使用情况的功能。
"""

import os
import argparse
from datetime import datetime, timedelta

# 导入数据库相关模块
try:
    from src.utils.db_utils import create_tables, get_db_session
    from src.models.db import ApiUsage
    from sqlalchemy import func, desc, cast, Date
    
    # 确保数据库表已创建
    create_tables()
    
    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败: {e}")
    DB_AVAILABLE = False

def get_user_usage(user_id, days=30):
    """获取用户的API使用情况"""
    if not DB_AVAILABLE:
        print("数据库模块不可用")
        return
    
    try:
        with get_db_session() as session:
            # 计算开始日期
            start_date = datetime.now() - timedelta(days=days)
            
            # 查询用户的API使用记录总数
            count = session.query(ApiUsage).filter(
                ApiUsage.user_id == user_id,
                ApiUsage.created_at >= start_date
            ).count()
            
            print(f"用户 {user_id} 在过去 {days} 天内的API调用总次数: {count}")
            
            # 查询用户的API使用记录按端点分组
            endpoint_counts = session.query(
                ApiUsage.endpoint, 
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.user_id == user_id,
                ApiUsage.created_at >= start_date
            ).group_by(ApiUsage.endpoint).all()
            
            print("按端点的API调用次数:")
            for endpoint, count in endpoint_counts:
                print(f"  - {endpoint}: {count}次")
            
            # 查询用户每天的API使用记录
            daily_counts = session.query(
                cast(ApiUsage.created_at, Date).label('date'),
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.user_id == user_id,
                ApiUsage.created_at >= start_date
            ).group_by('date').order_by('date').all()
            
            print("每天的API调用次数:")
            for date, count in daily_counts:
                print(f"  - {date}: {count}次")
            
            # 查询用户最近的API使用记录
            recent_calls = session.query(ApiUsage).filter(
                ApiUsage.user_id == user_id
            ).order_by(ApiUsage.created_at.desc()).limit(10).all()
            
            print(f"最近的API调用 (最多10条):")
            for i, call in enumerate(recent_calls, 1):
                status_str = "成功" if call.status == "success" else "失败"
                print(f"  {i}. 端点: {call.endpoint}, 查询: {call.query}, 状态: {status_str}, 时间: {call.created_at}")
    except Exception as e:
        print(f"获取用户API使用情况失败: {e}")

def get_top_users(days=30, limit=10):
    """获取API使用量最多的用户"""
    if not DB_AVAILABLE:
        print("数据库模块不可用")
        return
    
    try:
        with get_db_session() as session:
            # 计算开始日期
            start_date = datetime.now() - timedelta(days=days)
            
            # 查询API使用量最多的用户
            top_users = session.query(
                ApiUsage.user_id,
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.created_at >= start_date
            ).group_by(ApiUsage.user_id).order_by(desc('count')).limit(limit).all()
            
            print(f"过去 {days} 天内API使用量最多的 {limit} 个用户:")
            for i, (user_id, count) in enumerate(top_users, 1):
                print(f"  {i}. 用户: {user_id}, 调用次数: {count}")
    except Exception as e:
        print(f"获取API使用量最多的用户失败: {e}")

def get_endpoint_stats(days=30):
    """获取端点的使用统计"""
    if not DB_AVAILABLE:
        print("数据库模块不可用")
        return
    
    try:
        with get_db_session() as session:
            # 计算开始日期
            start_date = datetime.now() - timedelta(days=days)
            
            # 查询端点的使用统计
            endpoint_stats = session.query(
                ApiUsage.endpoint,
                func.count(ApiUsage.id).label('count'),
                func.avg(ApiUsage.execution_time).label('avg_time'),
                func.min(ApiUsage.execution_time).label('min_time'),
                func.max(ApiUsage.execution_time).label('max_time')
            ).filter(
                ApiUsage.created_at >= start_date
            ).group_by(ApiUsage.endpoint).order_by(desc('count')).all()
            
            print(f"过去 {days} 天内端点的使用统计:")
            for i, (endpoint, count, avg_time, min_time, max_time) in enumerate(endpoint_stats, 1):
                print(f"  {i}. 端点: {endpoint}")
                print(f"     调用次数: {count}")
                if avg_time is not None:
                    print(f"     平均执行时间: {avg_time:.2f}秒")
                if min_time is not None and max_time is not None:
                    print(f"     最短执行时间: {min_time:.2f}秒, 最长执行时间: {max_time:.2f}秒")
                print()
    except Exception as e:
        print(f"获取端点的使用统计失败: {e}")

def get_daily_stats(days=30):
    """获取每日的API使用统计"""
    if not DB_AVAILABLE:
        print("数据库模块不可用")
        return
    
    try:
        with get_db_session() as session:
            # 计算开始日期
            start_date = datetime.now() - timedelta(days=days)
            
            # 查询每日的API使用统计
            daily_stats = session.query(
                cast(ApiUsage.created_at, Date).label('date'),
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.created_at >= start_date
            ).group_by('date').order_by('date').all()
            
            print(f"过去 {days} 天内每日的API使用统计:")
            for date, count in daily_stats:
                print(f"  - {date}: {count}次")
    except Exception as e:
        print(f"获取每日的API使用统计失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="API使用管理工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 用户使用情况命令
    user_parser = subparsers.add_parser("user", help="获取用户的API使用情况")
    user_parser.add_argument("user_id", help="用户ID")
    user_parser.add_argument("--days", type=int, default=30, help="天数 (默认: 30)")
    
    # 顶级用户命令
    top_parser = subparsers.add_parser("top", help="获取API使用量最多的用户")
    top_parser.add_argument("--days", type=int, default=30, help="天数 (默认: 30)")
    top_parser.add_argument("--limit", type=int, default=10, help="用户数量 (默认: 10)")
    
    # 端点统计命令
    endpoint_parser = subparsers.add_parser("endpoint", help="获取端点的使用统计")
    endpoint_parser.add_argument("--days", type=int, default=30, help="天数 (默认: 30)")
    
    # 每日统计命令
    daily_parser = subparsers.add_parser("daily", help="获取每日的API使用统计")
    daily_parser.add_argument("--days", type=int, default=30, help="天数 (默认: 30)")
    
    args = parser.parse_args()
    
    if args.command == "user":
        get_user_usage(args.user_id, args.days)
    elif args.command == "top":
        get_top_users(args.days, args.limit)
    elif args.command == "endpoint":
        get_endpoint_stats(args.days)
    elif args.command == "daily":
        get_daily_stats(args.days)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
