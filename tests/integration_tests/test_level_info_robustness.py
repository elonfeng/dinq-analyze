#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证level_info健壮性

此脚本测试level_info处理的健壮性，包括：
1. 处理缺少years_of_experience字段的情况
2. 处理缺少evaluation_bars字段的情况
3. 处理level_info为None的情况
"""

import os
import sys
import json
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入相关模块
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

def create_mock_scholar_data_missing_fields(scholar_id="TEST_MISSING"):
    """创建缺少字段的模拟学者数据"""
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
            "top_tier_percentage": 30.0,
            "most_cited_paper": {
                "title": "Test Paper",
                "year": 2020,
                "venue": "Test Conference",
                "citations": 500
            }
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
        },
        "level_info": {
            # 缺少years_of_experience字段
            "level_cn": "P8",
            "level_us": "L7",
            "earnings": "$200,000",
            "justification": "Test Justification",
            # 缺少evaluation_bars字段
        }
    }

def create_mock_scholar_data_null_level_info(scholar_id="TEST_NULL"):
    """创建level_info为None的模拟学者数据"""
    data = create_mock_scholar_data_missing_fields(scholar_id)
    data["level_info"] = None
    return data

def test_level_info_robustness():
    """测试level_info处理的健壮性"""
    if not DB_AVAILABLE:
        print("\n数据库模块不可用，跳过测试")
        return False
    
    print("\n=== 测试level_info处理的健壮性 ===")
    
    # 1. 测试缺少字段的情况
    print("\n1. 测试缺少字段的情况...")
    scholar_id_missing = "TEST_MISSING"
    
    # 清除缓存（如果有）
    scholar_repo.delete_by_scholar_id(scholar_id_missing)
    print(f"✅ 已清除学者 {scholar_id_missing} 的缓存")
    
    # 创建模拟数据
    mock_data_missing = create_mock_scholar_data_missing_fields(scholar_id_missing)
    print(f"✅ 已创建缺少字段的模拟数据")
    
    # 保存数据到缓存
    success = save_scholar_to_cache(mock_data_missing, scholar_id_missing)
    if success:
        print(f"✅ 成功将缺少字段的学者数据保存到缓存")
    else:
        print(f"❌ 保存缺少字段的学者数据到缓存失败")
        return False
    
    # 2. 测试level_info为None的情况
    print("\n2. 测试level_info为None的情况...")
    scholar_id_null = "TEST_NULL"
    
    # 清除缓存（如果有）
    scholar_repo.delete_by_scholar_id(scholar_id_null)
    print(f"✅ 已清除学者 {scholar_id_null} 的缓存")
    
    # 创建模拟数据
    mock_data_null = create_mock_scholar_data_null_level_info(scholar_id_null)
    print(f"✅ 已创建level_info为None的模拟数据")
    
    # 保存数据到缓存
    success = save_scholar_to_cache(mock_data_null, scholar_id_null)
    if success:
        print(f"✅ 成功将level_info为None的学者数据保存到缓存")
    else:
        print(f"❌ 保存level_info为None的学者数据到缓存失败")
        return False
    
    # 3. 测试从缓存获取数据
    print("\n3. 测试从缓存获取数据...")
    
    # 从缓存获取缺少字段的数据
    cached_data_missing = get_scholar_from_cache(scholar_id_missing)
    if cached_data_missing:
        print(f"✅ 成功从缓存获取缺少字段的数据")
        
        # 验证level_info字段
        level_info = cached_data_missing.get('level_info', {})
        if level_info and isinstance(level_info, dict):
            print(f"✅ level_info字段存在且为字典")
            
            # 验证level_info中的字段
            if 'level_cn' in level_info and 'level_us' in level_info:
                print(f"✅ level_info中包含level_cn和level_us字段")
            else:
                print(f"❌ level_info中缺少level_cn或level_us字段")
                return False
            
            # 验证缺少的字段
            if 'years_of_experience' not in level_info:
                print(f"✅ level_info中确实缺少years_of_experience字段")
            else:
                print(f"❌ level_info中不应该包含years_of_experience字段")
                return False
            
            if 'evaluation_bars' not in level_info:
                print(f"✅ level_info中确实缺少evaluation_bars字段")
            else:
                print(f"❌ level_info中不应该包含evaluation_bars字段")
                return False
        else:
            print(f"❌ level_info字段不存在或不是字典")
            return False
    else:
        print(f"❌ 从缓存获取缺少字段的数据失败")
        return False
    
    # 从缓存获取level_info为None的数据
    cached_data_null = get_scholar_from_cache(scholar_id_null)
    if cached_data_null:
        print(f"✅ 成功从缓存获取level_info为None的数据")
        
        # 验证level_info字段
        level_info = cached_data_null.get('level_info')
        if level_info is None:
            print(f"✅ level_info字段确实为None")
        else:
            print(f"❌ level_info字段不为None")
            return False
    else:
        print(f"❌ 从缓存获取level_info为None的数据失败")
        return False
    
    print("\n=== level_info处理的健壮性测试完成 ===")
    return True

if __name__ == "__main__":
    test_level_info_robustness()
