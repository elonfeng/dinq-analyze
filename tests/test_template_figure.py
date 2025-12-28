#!/usr/bin/env python
# coding: UTF-8
"""
Test script for template figure functionality.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the template figure module
from server.services.scholar.template_figure_kimi import get_template_figure

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'template_figure_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('template_figure_test')

def test_template_figure():
    """
    Test the template figure functionality.
    """
    # 测试数据
    test_data = {
        "researcher": {
            "name": "John Smith",
            "affiliation": "Stanford University",
            "h_index": 25,
            "total_citations": 5000,
            "research_fields": ["Artificial Intelligence", "Computer Vision", "Deep Learning"]
        },
        "publication_stats": {
            "total_papers": 80,
            "first_author_papers": 30,
            "first_author_percentage": 37.5,
            "last_author_papers": 20,
            "last_author_percentage": 25,
            "top_tier_papers": 25,
            "top_tier_percentage": 31.25,
            "citation_stats": {
                "total_citations": 5000,
                "max_citations": 800,
                "avg_citations": 62.5,
                "median_citations": 35
            },
            "conference_distribution": {
                "CVPR": 10,
                "ICCV": 8,
                "NeurIPS": 7,
                "ICLR": 5,
                "ECCV": 4,
                "AAAI": 3,
                "ICML": 3,
                "ACL": 2
            },
            "journal_distribution": {
                "TPAMI": 5,
                "IJCV": 3,
                "TIP": 2
            },
            "most_cited_paper": {
                "title": "Deep Learning Applications in Computer Vision",
                "year": "2018",
                "venue": "CVPR 2018",
                "citations": 800,
                "authors": ["John Smith", "Michael Johnson", "Sarah Williams"]
            }
        },
        "most_frequent_collaborator": {
            "full_name": "Michael Johnson",
            "affiliation": "MIT",
            "research_interests": ["Computer Vision", "Deep Learning"],
            "scholar_id": "abcdef123456",
            "coauthored_papers": 25,
            "best_paper": {
                "title": "Deep Learning Applications in Computer Vision",
                "year": "2018",
                "venue": "CVPR 2018",
                "citations": 800
            },
            "h_index": 20,
            "total_citations": 3500
        }
    }

    # 获取角色模型
    logger.info("Testing get_template_figure function")
    role_model = get_template_figure(test_data)

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join('tests/results', f"template_figure_test_{timestamp}")
    os.makedirs(result_dir, exist_ok=True)

    result_file = os.path.join(result_dir, "role_model.json")
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(role_model, f, ensure_ascii=False, indent=2)

    logger.info(f"Results saved to {result_file}")

    # 打印角色模型信息
    logger.info(f"Role model name: {role_model.get('name', 'N/A')}")
    logger.info(f"Role model institution: {role_model.get('institution', 'N/A')}")
    logger.info(f"Role model position: {role_model.get('position', 'N/A')}")
    logger.info(f"Role model photo URL: {role_model.get('photo_url', 'N/A')}")
    logger.info(f"Role model achievement: {role_model.get('achievement', 'N/A')[:100]}...")
    logger.info(f"Role model similarity reason: {role_model.get('similarity_reason', 'N/A')[:100]}...")

    return role_model

if __name__ == "__main__":
    test_template_figure()
