#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证数据库缓存功能（使用模拟数据）

此脚本测试数据库缓存功能，使用模拟数据。
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
        "most_cited_ai_paper": {
            "name": "Test Paper",
            "arxiv_url": "https://arxiv.org/abs/1234.5678",
            "image": "https://example.com/image.jpg"
        },
        "paper_news": {
            "news": "Test News",
            "date": "2023-01-01",
            "description": "Test Description",
            "url": "https://example.com/news"
        },
        "role_model": {
            "name": "Role Model",
            "institution": "Role Model University",
            "position": "Professor",
            "photo_url": "https://example.com/photo.jpg",
            "achievement": "Test Achievement",
            "similarity_reason": "Test Similarity Reason"
        },
        "level_info": {
            "years_of_experience": {"years": 10},
            "level_cn": "P8",
            "level_us": "L7",
            "earnings": "$200,000",
            "justification": "Test Justification",
            "evaluation_bars": {
                "depth_vs_breadth": {"score": 0.7},
                "theory_vs_practice": {"score": 0.6},
                "individual_vs_team": {"score": 0.5}
            }
        }
    }

def test_db_cache_mock():
    """测试数据库缓存功能（使用模拟数据）"""
    if not DB_AVAILABLE:
        print("\n数据库模块不可用，跳过测试")
        return False
    
    print("\n=== 测试数据库缓存功能（使用模拟数据）===")
    
    # 使用模拟的学者ID
    scholar_id = "TEST123456"
    
    # 1. 清除缓存（如果有）
    print("\n1. 清除缓存（如果有）...")
    scholar_repo.delete_by_scholar_id(scholar_id)
    print(f"✅ 已清除学者 {scholar_id} 的缓存")
    
    # 2. 创建模拟数据
    print("\n2. 创建模拟数据...")
    mock_data = create_mock_scholar_data(scholar_id)
    print(f"✅ 已创建模拟数据")
    
    # 3. 保存数据到缓存
    print("\n3. 保存数据到缓存...")
    success = save_scholar_to_cache(mock_data, scholar_id)
    if success:
        print(f"✅ 成功将学者 {scholar_id} 的数据保存到缓存")
    else:
        print(f"❌ 保存学者 {scholar_id} 的数据到缓存失败")
        return False
    
    # 4. 从缓存获取数据
    print("\n4. 从缓存获取数据...")
    cached_data = get_scholar_from_cache(scholar_id)
    if cached_data:
        print(f"✅ 成功从缓存获取数据")
        
        # 验证数据
        if cached_data["researcher"]["name"] == mock_data["researcher"]["name"] and \
           cached_data["researcher"]["h_index"] == mock_data["researcher"]["h_index"] and \
           cached_data["publication_stats"]["total_papers"] == mock_data["publication_stats"]["total_papers"]:
            print(f"✅ 缓存数据验证成功")
        else:
            print(f"❌ 缓存数据验证失败")
            return False
        
        # 验证是否包含所有额外字段
        for field in ["most_cited_ai_paper", "paper_news", "role_model", "level_info"]:
            if field in cached_data:
                print(f"✅ 缓存数据包含 {field} 字段")
            else:
                print(f"❌ 缓存数据不包含 {field} 字段")
                return False
    else:
        print(f"❌ 从缓存获取数据失败")
        return False
    
    # 5. 测试缓存过期
    print("\n5. 测试缓存过期...")
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
    
    print("\n=== 数据库缓存功能测试完成（使用模拟数据）===")
    return True

if __name__ == "__main__":
    test_db_cache_mock()
