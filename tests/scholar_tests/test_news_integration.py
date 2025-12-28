#!/usr/bin/env python
# coding: UTF-8
"""
Test script for paper news integration.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.analyzer import ScholarAnalyzer
from onepage.signature_news import get_latest_news

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'news_integration_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('news_integration_test')

def test_news_integration():
    """
    Test the integration of paper news functionality.
    """
    logger.info("Testing paper news integration")
    
    # Create mock author data
    author_data = {
        "name": "Test Researcher",
        "papers": [
            {
                "title": "Attention is All You Need",
                "year": "2017",
                "venue": "Neural Information Processing Systems",
                "citations": 1000,
                "authors": ["Test Researcher", "Collaborator One"]
            }
        ]
    }
    
    # Initialize the analyzer
    analyzer = ScholarAnalyzer()
    
    # Analyze publications
    pub_stats = analyzer.analyze_publications(author_data)
    
    # Check if paper_news field exists
    if 'paper_news' in pub_stats:
        logger.info("paper_news field exists in publication stats")
        
        # Check if paper_news has content
        paper_news = pub_stats['paper_news']
        if paper_news:
            logger.info("Paper news content found:")
            logger.info(f"Title: {paper_news.get('news')}")
            logger.info(f"Date: {paper_news.get('date')}")
            logger.info(f"URL: {paper_news.get('url')}")
        else:
            logger.warning("paper_news field exists but is empty")
    else:
        logger.error("paper_news field does not exist in publication stats")
    
    # Save the results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join('tests/scholar_tests/results', f"news_integration_{timestamp}")
    os.makedirs(result_dir, exist_ok=True)
    
    result_file = os.path.join(result_dir, "publication_stats.json")
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(pub_stats, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Results saved to {result_file}")
    
    return pub_stats

if __name__ == "__main__":
    test_news_integration()
