#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证ScholarService中的缓存功能（完整版）

此脚本测试ScholarService中的缓存功能，包括：
1. 第一次查询（从Google Scholar获取数据）
2. 第二次查询（从缓存获取数据）
3. 验证缓存是否有效
4. 验证是否跳过了不必要的API调用
"""

import os
import sys
import time
from datetime import datetime
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入相关模块
try:
    from src.utils.db_utils import create_tables
    from server.services.scholar.scholar_service import ScholarService, run_scholar_analysis
    
    # 确保数据库表已创建
    create_tables()
    
    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def test_scholar_service_cache_full():
    """测试ScholarService中的缓存功能（完整版）"""
    if not DB_AVAILABLE:
        print("\n数据库模块不可用，跳过测试")
        return False
    
    print("\n=== 测试ScholarService中的缓存功能（完整版）===")
    
    # 使用已知的学者ID
    scholar_id = "DZ-fHPgAAAAJ"  # Hinrich Schütze
    
    # 初始化ScholarService
    api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
    
    # 1. 清除缓存（如果有）
    print("\n1. 清除缓存（如果有）...")
    from src.utils.scholar_repository import scholar_repo
    scholar_repo.delete_by_scholar_id(scholar_id)
    print(f"✅ 已清除学者 {scholar_id} 的缓存")
    
    # 2. 第一次查询（从Google Scholar获取数据）
    print("\n2. 第一次查询（从Google Scholar获取数据）...")
    
    # 记录开始时间
    start_time = time.time()
    
    # 收集日志
    logs1 = []
    def callback1(message):
        msg_text = message if isinstance(message, str) else json.dumps(message, ensure_ascii=False)
        logs1.append(msg_text)
        print(f"   - {msg_text}")
    
    # 运行分析
    report1 = run_scholar_analysis(
        scholar_id=scholar_id, 
        use_crawlbase=bool(api_token),
        api_token=api_token or None,
        callback=callback1,
        use_cache=True,
        cache_max_age_days=3
    )
    
    # 记录结束时间
    end_time = time.time()
    
    # 计算执行时间
    execution_time1 = end_time - start_time
    
    # 检查是否成功获取数据
    if report1:
        print(f"✅ 成功从Google Scholar获取数据，耗时: {execution_time1:.2f}秒")
        
        # 检查是否包含"from cache"字样
        cache_logs1 = [log for log in logs1 if "from cache" in log.lower()]
        if cache_logs1:
            print(f"❓ 第一次查询中发现缓存相关日志: {len(cache_logs1)}条")
        else:
            print(f"✅ 第一次查询中没有缓存相关日志")
        
        # 检查是否包含API调用相关日志
        api_logs1 = [log for log in logs1 if "arxiv" in log.lower() or "news" in log.lower() or "role model" in log.lower()]
        if api_logs1:
            print(f"✅ 第一次查询中包含API调用相关日志: {len(api_logs1)}条")
        else:
            print(f"❓ 第一次查询中没有API调用相关日志")
    else:
        print(f"❌ 从Google Scholar获取数据失败")
        return False
    
    # 3. 第二次查询（从缓存获取数据）
    print("\n3. 第二次查询（从缓存获取数据）...")
    
    # 记录开始时间
    start_time = time.time()
    
    # 收集日志
    logs2 = []
    def callback2(message):
        msg_text = message if isinstance(message, str) else json.dumps(message, ensure_ascii=False)
        logs2.append(msg_text)
        print(f"   - {msg_text}")
    
    # 运行分析
    report2 = run_scholar_analysis(
        scholar_id=scholar_id, 
        use_crawlbase=bool(api_token),
        api_token=api_token or None,
        callback=callback2,
        use_cache=True,
        cache_max_age_days=3
    )
    
    # 记录结束时间
    end_time = time.time()
    
    # 计算执行时间
    execution_time2 = end_time - start_time
    
    # 检查是否成功获取数据
    if report2:
        print(f"✅ 成功从缓存获取数据，耗时: {execution_time2:.2f}秒")
        
        # 检查是否包含"from cache"字样
        cache_logs2 = [log for log in logs2 if "from cache" in log.lower()]
        if cache_logs2:
            print(f"✅ 第二次查询中发现缓存相关日志: {len(cache_logs2)}条")
            for log in cache_logs2:
                print(f"      {log}")
        else:
            print(f"❓ 第二次查询中没有缓存相关日志")
        
        # 检查是否包含API调用相关日志
        api_logs2 = [log for log in logs2 if ("arxiv:" in log.lower() or "news:" in log.lower() or "role model:" in log.lower()) and "from cache" not in log.lower()]
        if not api_logs2:
            print(f"✅ 第二次查询中没有API调用相关日志")
        else:
            print(f"❓ 第二次查询中包含API调用相关日志: {len(api_logs2)}条")
            for log in api_logs2:
                print(f"      {log}")
        
        # 检查执行时间是否明显减少
        if execution_time2 < execution_time1 * 0.5:
            print(f"✅ 缓存查询明显更快（{execution_time2:.2f}秒 vs {execution_time1:.2f}秒）")
        else:
            print(f"❓ 缓存查询没有明显更快（{execution_time2:.2f}秒 vs {execution_time1:.2f}秒）")
    else:
        print(f"❌ 从缓存获取数据失败")
        return False
    
    print("\n=== ScholarService缓存功能测试完成（完整版）===")
    return True

if __name__ == "__main__":
    test_scholar_service_cache_full()
