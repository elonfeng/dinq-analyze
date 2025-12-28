#!/usr/bin/env python
# coding: UTF-8
"""
Test script for best collaborator integration.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.scholar_service import ScholarService
from onepage.openrouter_author_list import get_author_detail

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'best_collaborator_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('best_collaborator_test')

def test_get_author_detail():
    """
    Test the get_author_detail function directly.
    """
    logger.info("Testing get_author_detail function directly")

    # 准备测试数据
    coauthor_info = json.dumps({
        'name': 'Geoffrey Hinton',
        'coauthored_papers': 5,
        'best_paper': {
            'title': 'ImageNet Classification with Deep Convolutional Neural Networks',
            'year': '2012',
            'venue': 'NeurIPS 2012',
            'citations': 100000
        }
    })

    # 调用函数
    author_details = get_author_detail(coauthor_info)

    # 打印结果
    logger.info("Author details:")
    for key, value in author_details.items():
        logger.info(f"{key}: {value}")

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join('tests/scholar_tests/results', f"author_detail_{timestamp}")
    os.makedirs(result_dir, exist_ok=True)

    result_file = os.path.join(result_dir, "author_detail.json")
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(author_details, f, ensure_ascii=False, indent=2)

    logger.info(f"Results saved to {result_file}")

    return author_details

def test_best_collaborator_integration():
    """
    Test the best collaborator integration with mock data.
    """
    logger.info("Testing best collaborator integration with mock data")

    # 创建 ScholarService 实例
    service = ScholarService()

    # 创建模拟数据
    author_data = {
        "name": "Test Researcher",
        "papers": [
            {
                "title": "Attention is All You Need",
                "year": "2017",
                "venue": "Neural Information Processing Systems",
                "citations": 1000,
                "authors": ["Test Researcher", "Geoffrey Hinton", "Yann LeCun"]
            },
            {
                "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                "year": "2018",
                "venue": "ACL",
                "citations": 500,
                "authors": ["Test Researcher", "Geoffrey Hinton"]
            },
            {
                "title": "Deep Residual Learning for Image Recognition",
                "year": "2016",
                "venue": "CVPR",
                "citations": 800,
                "authors": ["Test Researcher", "Geoffrey Hinton", "Andrew Ng"]
            }
        ]
    }

    # 分析合作者
    analyzer = service.analyzer
    coauthor_stats = analyzer.analyze_coauthors(author_data)

    # 使用 ScholarService 的内部方法直接处理 author_data
    # 由于 generate_report 方法不接受 author_data 参数，我们需要手动构建报告

    # 分析出版物
    pub_stats = analyzer.analyze_publications(author_data)

    # 计算研究者评级
    rating = analyzer.calculate_researcher_rating(author_data, pub_stats, coauthor_stats)

    # 获取最佳合作者信息
    most_frequent_collaborator = None
    if coauthor_stats and 'top_coauthors' in coauthor_stats and coauthor_stats['top_coauthors']:
        top_coauthor = coauthor_stats['top_coauthors'][0]
        coauthor_name = top_coauthor['name']

        # 准备传递给 get_author_detail 的信息
        coauthor_info = json.dumps({
            'name': coauthor_name,
            'coauthored_papers': top_coauthor['coauthored_papers'],
            'best_paper': top_coauthor.get('best_paper', {})
        })

        # 使用 get_author_detail 函数获取作者详情
        author_details = get_author_detail(coauthor_info)

        if author_details and author_details.get('name') != 'Unknown':
            logger.info(f"Successfully retrieved details for collaborator {coauthor_name} using get_author_detail")

            # 创建最佳合作者对象
            most_frequent_collaborator = {
                'full_name': author_details.get('name', coauthor_name),
                'affiliation': author_details.get('affiliation', 'Unknown'),
                'research_interests': [],  # get_author_detail 不提供研究兴趣
                'scholar_id': '',  # get_author_detail 不提供学者ID
                'coauthored_papers': top_coauthor['coauthored_papers'],
                'best_paper': top_coauthor['best_paper'],
                'h_index': 'N/A',
                'total_citations': 'N/A',
                'photo': author_details.get('photo'),  # 添加照片URL
                'graduate_school': author_details.get('graduate_school'),  # 添加毕业学校
                'description': author_details.get('description')  # 添加描述
            }

    # 如果没有找到最佳合作者，创建一个空的合作者对象
    if most_frequent_collaborator is None:
        logger.warning("No most frequent collaborator found or error occurred. Creating empty collaborator object.")
        most_frequent_collaborator = {
            'full_name': 'No frequent collaborator found',
            'affiliation': 'N/A',
            'research_interests': [],
            'scholar_id': '',
            'coauthored_papers': 0,
            'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0},
            'h_index': 'N/A',
            'total_citations': 'N/A'
        }

    # 构建报告
    report = {
        'researcher': {
            'name': author_data.get('name', ''),
        },
        'publication_stats': pub_stats,
        'coauthor_stats': coauthor_stats,
        'rating': rating,
        'most_frequent_collaborator': most_frequent_collaborator
    }

    # 获取最佳合作者信息
    most_frequent_collaborator = report.get('most_frequent_collaborator', {})

    # 打印结果
    logger.info("Most frequent collaborator:")
    for key, value in most_frequent_collaborator.items():
        if key != 'best_paper':
            logger.info(f"{key}: {value}")

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join('tests/scholar_tests/results', f"best_collaborator_{timestamp}")
    os.makedirs(result_dir, exist_ok=True)

    result_file = os.path.join(result_dir, "best_collaborator.json")
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(most_frequent_collaborator, f, ensure_ascii=False, indent=2)

    logger.info(f"Results saved to {result_file}")

    return most_frequent_collaborator

if __name__ == "__main__":
    # 测试 get_author_detail 函数
    test_get_author_detail()

    # 测试最佳合作者集成
    test_best_collaborator_integration()
