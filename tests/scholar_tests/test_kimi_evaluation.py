#!/usr/bin/env python
# coding: UTF-8
"""
Test script for Kimi evaluation functionality.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.utils.kimi_evaluator import generate_critical_evaluation, format_researcher_data_for_critique

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'kimi_evaluation_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('kimi_evaluation_test')

def test_kimi_evaluation():
    """
    Test the Kimi evaluation functionality with mock data.
    """
    logger.info("Testing Kimi evaluation with mock data")

    # Create mock data in English
    mock_data = {
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
            "year_distribution": {
                "2023": 8,
                "2022": 10,
                "2021": 12,
                "2020": 9,
                "2019": 7,
                "2018": 6,
                "2017": 5
            },
            "most_cited_paper": {
                "title": "Deep Learning Applications in Computer Vision",
                "year": "2018",
                "venue": "CVPR 2018",
                "citations": 800,
                "authors": ["John Smith", "Michael Johnson", "Sarah Williams"]
            }
        },
        "coauthor_stats": {
            "total_coauthors": 45,
            "collaboration_index": 3.2,
            "top_coauthors": [
                {
                    "name": "Michael Johnson",
                    "coauthored_papers": 25,
                    "best_paper": {
                        "title": "Deep Learning Applications in Computer Vision",
                        "year": "2018",
                        "venue": "CVPR 2018",
                        "citations": 800
                    }
                },
                {
                    "name": "Sarah Williams",
                    "coauthored_papers": 18,
                    "best_paper": {
                        "title": "New Methods in Self-Supervised Learning",
                        "year": "2020",
                        "venue": "NeurIPS 2020",
                        "citations": 450
                    }
                }
            ]
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
        },
        "research_style": {
            "depth_vs_breadth": "More focused on depth",
            "theory_vs_practice": "Balance of theory and practice",
            "individual_vs_team": "More focused on team collaboration"
        },
        "rating": {
            "overall_rating": 8.5,
            "impact_rating": 8.7,
            "productivity_rating": 8.3,
            "innovation_rating": 8.6
        }
    }

    # 格式化研究者数据
    formatted_data = format_researcher_data_for_critique(mock_data)
    logger.info("Formatted researcher data:")
    logger.info(formatted_data)

    # 生成评论
    evaluation = generate_critical_evaluation(mock_data)

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join('tests/scholar_tests/results', f"kimi_evaluation_{timestamp}")
    os.makedirs(result_dir, exist_ok=True)

    # 保存格式化数据
    formatted_file = os.path.join(result_dir, "formatted_data.txt")
    with open(formatted_file, 'w', encoding='utf-8') as f:
        f.write(formatted_data)

    # 保存评论
    evaluation_file = os.path.join(result_dir, "evaluation.txt")
    with open(evaluation_file, 'w', encoding='utf-8') as f:
        f.write(evaluation)

    logger.info(f"Results saved to {result_dir}")
    logger.info(f"Evaluation length: {len(evaluation)} characters")

    # Check if the evaluation length meets the requirements
    word_count = len(evaluation.split())
    if 400 <= word_count <= 500:
        logger.info(f"Evaluation length ({word_count} words) is within the 400-500 word limit")
    elif word_count < 400:
        logger.warning(f"Evaluation length ({word_count} words) is below the 400 word minimum")
    else:
        logger.warning(f"Evaluation length ({word_count} words) exceeds the 500 word maximum")

    # Print the first 150 characters of the evaluation
    logger.info(f"Evaluation preview: {evaluation[:150]}...")

    # Check if the evaluation is in English
    non_english_chars = sum(1 for char in evaluation if ord(char) > 127 and char not in '.,;:!?"\'\'()[]{}')
    if non_english_chars > 10:  # Allow a few non-English characters for special terms
        logger.warning(f"Evaluation contains {non_english_chars} non-English characters")
    else:
        logger.info("Evaluation is in English")

    return evaluation

if __name__ == "__main__":
    test_kimi_evaluation()
