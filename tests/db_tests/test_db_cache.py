#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证数据库缓存功能

此脚本测试数据库缓存功能，包括：
1. 将模拟数据保存到数据库
2. 从数据库缓存中获取数据
3. 验证数据是否正确
"""

import os
import sys
import json
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入数据库相关模块
try:
    from src.utils.db_utils import create_tables
    from src.utils.scholar_repository import scholar_repo
    from server.api.scholar.db_cache import get_scholar_from_cache, save_scholar_to_cache
    
    # 确保数据库表已创建
    create_tables()
    
    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def create_mock_scholar_data(scholar_id="TEST123456"):
    """创建模拟学者数据"""
    return {
        "researcher": {
            "name": "Test Researcher",
            "abbreviated_name": "T. Researcher",
            "affiliation": "Test University",
            "email": "test@example.com",
            "research_fields": ["AI", "Machine Learning", "Computer Vision"],
            "total_citations": 1000,
            "citations_5y": 500,
            "h_index": 20,
            "h_index_5y": 15,
            "yearly_citations": {
                "2020": 100,
                "2021": 200,
                "2022": 300,
                "2023": 400
            },
            "scholar_id": scholar_id
        },
        "publication_stats": {
            "total_papers": 50,
            "first_author_papers": 20,
            "first_author_percentage": 40.0,
            "top_tier_papers": 15,
            "top_tier_percentage": 30.0
        },
        "coauthor_stats": {
            "total_coauthors": 30,
            "top_coauthors": [
                {"name": "Coauthor 1", "papers": 10},
                {"name": "Coauthor 2", "papers": 8},
                {"name": "Coauthor 3", "papers": 5}
            ]
        },
        "rating": {
            "overall_score": 8.5,
            "level": "Senior Researcher"
        },
        "most_frequent_collaborator": {
            "full_name": "Coauthor 1",
            "affiliation": "Partner University",
            "research_interests": ["AI", "NLP"],
            "scholar_id": "COLLAB123",
            "coauthored_papers": 10,
            "h_index": 25,
            "total_citations": 2000
        }
    }

def test_db_cache():
    """测试数据库缓存功能"""
    if not DB_AVAILABLE:
        print("\n数据库模块不可用，跳过测试")
        return False
    
    print("\n=== 测试数据库缓存功能 ===")
    
    # 创建模拟数据
    scholar_id = "TEST123456"
    scholar_data = create_mock_scholar_data(scholar_id)
    
    # 1. 清除缓存（如果有）
    print("\n1. 清除缓存（如果有）...")
    scholar_repo.delete_by_scholar_id(scholar_id)
    print(f"✅ 已清除学者 {scholar_id} 的缓存")
    
    # 2. 保存数据到缓存
    print("\n2. 保存数据到缓存...")
    success = save_scholar_to_cache(scholar_data, scholar_id)
    if success:
        print(f"✅ 成功将学者 {scholar_id} 的数据保存到缓存")
    else:
        print(f"❌ 保存学者 {scholar_id} 的数据到缓存失败")
        return False
    
    # 3. 从缓存获取数据
    print("\n3. 从缓存获取数据...")
    cached_data = get_scholar_from_cache(scholar_id)
    if cached_data:
        print(f"✅ 成功从缓存获取数据")
        
        # 验证数据
        if cached_data["researcher"]["name"] == scholar_data["researcher"]["name"] and \
           cached_data["researcher"]["h_index"] == scholar_data["researcher"]["h_index"] and \
           cached_data["publication_stats"]["total_papers"] == scholar_data["publication_stats"]["total_papers"]:
            print(f"✅ 缓存数据验证成功")
        else:
            print(f"❌ 缓存数据验证失败")
            return False
    else:
        print(f"❌ 从缓存获取数据失败")
        return False
    
    # 4. 测试缓存过期
    print("\n4. 测试缓存过期...")
    # 默认缓存有效期为3天，所以应该不会过期
    expired_data = get_scholar_from_cache(scholar_id, max_age_days=3)
    if expired_data:
        print(f"✅ 缓存未过期，成功获取数据")
    else:
        print(f"❌ 缓存已过期，无法获取数据")
        return False
    
    # 设置缓存有效期为0天，应该会过期
    expired_data = get_scholar_from_cache(scholar_id, max_age_days=0)
    if not expired_data:
        print(f"✅ 缓存已过期，无法获取数据")
    else:
        print(f"❌ 缓存未过期，成功获取数据")
        return False
    
    print("\n=== 数据库缓存功能测试完成 ===")
    return True

if __name__ == "__main__":
    test_db_cache()
