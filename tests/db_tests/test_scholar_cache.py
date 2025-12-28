#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证学者数据库缓存功能

此脚本测试学者数据库缓存功能，包括：
1. 从数据库缓存中获取学者数据
2. 将学者数据保存到数据库缓存
3. 验证缓存是否有效
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
    from server.services.scholar.scholar_service import ScholarService
    
    # 确保数据库表已创建
    create_tables()
    
    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def test_scholar_cache(scholar_id="ZUeyIxMAAAAJ", researcher_name="Daiheng Gao"):
    """测试学者数据库缓存功能"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过测试")
        return False
    
    print(f"=== 测试学者数据库缓存功能 ===")
    print(f"学者ID: {scholar_id}")
    print(f"学者姓名: {researcher_name}")
    
    # 1. 检查缓存中是否已有数据
    print("\n1. 检查缓存中是否已有数据...")
    cached_data = get_cached_scholar(scholar_id)
    if cached_data:
        print(f"✅ 缓存中已有学者 {scholar_id} 的数据")
        print(f"   姓名: {cached_data.get('name', 'unknown')}")
        print(f"   机构: {cached_data.get('affiliation', 'unknown')}")
        print(f"   最后更新时间: {cached_data.get('last_updated', 'unknown')}")
        
        # 询问是否继续测试
        response = input("\n是否继续测试并重新获取数据? (y/n): ")
        if response.lower() != 'y':
            return True
    else:
        print(f"❌ 缓存中没有学者 {scholar_id} 的数据")
    
    # 2. 从Google Scholar获取数据
    print("\n2. 从Google Scholar获取数据...")
    api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
    scholar_service = ScholarService(use_crawlbase=bool(api_token), api_token=api_token or None)
    
    # 开始计时
    t1 = time.time()
    
    # 生成报告
    try:
        report = scholar_service.generate_report(scholar_id=scholar_id)
        if report is None:
            print(f"❌ 无法为ID {scholar_id} 生成报告")
            return False
        
        # 打印执行时间
        print(f"✅ 分析完成，耗时 {time.time() - t1:.2f} 秒")
    except Exception as e:
        print(f"❌ 生成报告时出错: {str(e)}")
        return False
    
    # 3. 保存数据到缓存
    print("\n3. 保存数据到缓存...")
    success = save_scholar_to_cache(report, scholar_id)
    if success:
        print(f"✅ 成功将学者 {scholar_id} 的数据保存到缓存")
    else:
        print(f"❌ 保存学者 {scholar_id} 的数据到缓存失败")
        return False
    
    # 4. 再次从缓存获取数据
    print("\n4. 再次从缓存获取数据...")
    cached_data = get_scholar_from_cache(scholar_id)
    if cached_data:
        print(f"✅ 从缓存成功获取到学者 {scholar_id} 的数据")
        
        # 打印一些基本信息
        researcher = cached_data.get('researcher', {})
        print(f"   姓名: {researcher.get('name', 'unknown')}")
        print(f"   机构: {researcher.get('affiliation', 'unknown')}")
        print(f"   h指数: {researcher.get('h_index', 'unknown')}")
        print(f"   总引用: {researcher.get('total_citations', 'unknown')}")
        
        # 打印报告的顶级键
        print("\n报告结构:")
        for key in cached_data.keys():
            print(f"- {key}")
    else:
        print(f"❌ 从缓存获取学者 {scholar_id} 的数据失败")
        return False
    
    print("\n=== 学者数据库缓存功能测试完成 ===")
    return True

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='测试学者数据库缓存功能')
    parser.add_argument('--id', type=str, default="ZUeyIxMAAAAJ", help='Google Scholar ID')
    parser.add_argument('--name', type=str, default="Daiheng Gao", help='研究者姓名')
    
    args = parser.parse_args()
    
    test_scholar_cache(scholar_id=args.id, researcher_name=args.name)

if __name__ == "__main__":
    main()
