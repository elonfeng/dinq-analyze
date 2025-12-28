#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证ScholarService中的缓存功能

此脚本测试ScholarService中的缓存功能，包括：
1. 第一次查询（从Google Scholar获取数据）
2. 第二次查询（从缓存获取数据）
3. 验证缓存是否有效
"""

import os
import sys
import time
from datetime import datetime

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

def test_scholar_service_cache():
    """测试ScholarService中的缓存功能"""
    if not DB_AVAILABLE:
        print("\n数据库模块不可用，跳过测试")
        return False
    
    print("\n=== 测试ScholarService中的缓存功能 ===")
    
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
    
    # 创建服务实例，启用缓存
    scholar_service = ScholarService(use_crawlbase=bool(api_token), api_token=api_token or None, use_cache=True, cache_max_age_days=3)
    
    # 生成报告
    report1 = scholar_service.generate_report(scholar_id=scholar_id)
    
    # 记录结束时间
    end_time = time.time()
    
    # 计算执行时间
    execution_time1 = end_time - start_time
    
    # 检查是否成功获取数据
    if report1:
        print(f"✅ 成功从Google Scholar获取数据，耗时: {execution_time1:.2f}秒")
        
        # 打印一些基本信息
        print(f"   姓名: {report1['researcher']['name']}")
        print(f"   机构: {report1['researcher']['affiliation']}")
        print(f"   h指数: {report1['researcher']['h_index']}")
        print(f"   总引用: {report1['researcher']['total_citations']}")
    else:
        print(f"❌ 从Google Scholar获取数据失败")
        return False
    
    # 3. 第二次查询（从缓存获取数据）
    print("\n3. 第二次查询（从缓存获取数据）...")
    
    # 记录开始时间
    start_time = time.time()
    
    # 创建新的服务实例，启用缓存
    scholar_service2 = ScholarService(use_crawlbase=bool(api_token), api_token=api_token or None, use_cache=True, cache_max_age_days=3)
    
    # 生成报告
    report2 = scholar_service2.generate_report(scholar_id=scholar_id)
    
    # 记录结束时间
    end_time = time.time()
    
    # 计算执行时间
    execution_time2 = end_time - start_time
    
    # 检查是否成功获取数据
    if report2:
        print(f"✅ 成功从缓存获取数据，耗时: {execution_time2:.2f}秒")
        
        # 打印一些基本信息
        print(f"   姓名: {report2['researcher']['name']}")
        print(f"   机构: {report2['researcher']['affiliation']}")
        print(f"   h指数: {report2['researcher']['h_index']}")
        print(f"   总引用: {report2['researcher']['total_citations']}")
        
        # 检查执行时间是否明显减少
        if execution_time2 < execution_time1 * 0.5:
            print(f"✅ 缓存查询明显更快（{execution_time2:.2f}秒 vs {execution_time1:.2f}秒）")
        else:
            print(f"❓ 缓存查询没有明显更快（{execution_time2:.2f}秒 vs {execution_time1:.2f}秒）")
    else:
        print(f"❌ 从缓存获取数据失败")
        return False
    
    # 4. 测试run_scholar_analysis函数
    print("\n4. 测试run_scholar_analysis函数...")
    
    # 记录开始时间
    start_time = time.time()
    
    # 运行分析
    report3 = run_scholar_analysis(
        scholar_id=scholar_id, 
        use_crawlbase=True, 
        api_token=api_token,
        use_cache=True,
        cache_max_age_days=3
    )
    
    # 记录结束时间
    end_time = time.time()
    
    # 计算执行时间
    execution_time3 = end_time - start_time
    
    # 检查是否成功获取数据
    if report3:
        print(f"✅ 成功从缓存获取数据，耗时: {execution_time3:.2f}秒")
        
        # 检查执行时间是否明显减少
        if execution_time3 < execution_time1 * 0.5:
            print(f"✅ 缓存查询明显更快（{execution_time3:.2f}秒 vs {execution_time1:.2f}秒）")
        else:
            print(f"❓ 缓存查询没有明显更快（{execution_time3:.2f}秒 vs {execution_time1:.2f}秒）")
    else:
        print(f"❌ 从缓存获取数据失败")
        return False
    
    print("\n=== ScholarService缓存功能测试完成 ===")
    return True

if __name__ == "__main__":
    test_scholar_service_cache()
