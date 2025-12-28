#!/usr/bin/env python
# coding: UTF-8
"""
Test script for paper news information generation in the scholar service.
"""

import os
import sys
import json
import argparse
import glob
import logging
from tqdm import tqdm
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.analyzer import ScholarAnalyzer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'paper_news_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('paper_news_test')

def test_paper_news(report_file=None, paper_title=None, output_dir='tests/scholar_tests/results'):
    """
    Test the paper news information generation functionality.

    Args:
        report_file (str, optional): Path to the scholar report JSON file
        paper_title (str, optional): Paper title to get news for
        output_dir (str): Directory to save the output

    Returns:
        dict: Paper news information if successful, None otherwise
    """
    # Ensure output directory exists
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join(output_dir, f"paper_news_{timestamp}")
    os.makedirs(result_dir, exist_ok=True)

    # Initialize the analyzer
    analyzer = ScholarAnalyzer()

    # Get the paper title
    if report_file:
        logger.info(f"Testing paper news information generation for {report_file}...")

        # Load the report
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
        except Exception as e:
            logger.error(f"Error loading report: {e}")
            return None

        # Get the most cited paper title
        most_cited_paper = report.get('most_cited_paper', {})
        title = most_cited_paper.get('title', 'Unknown Title')
    elif paper_title:
        logger.info(f"Testing paper news information generation for title: {paper_title}")
        title = paper_title
    else:
        logger.error("Either report_file or paper_title must be provided")
        return None

    # Generate paper news information
    try:
        logger.info(f"Getting news for paper: {title}")
        news_info = analyzer.get_paper_news(title)
        if news_info:
            logger.info(f"Paper news information generated successfully")
        else:
            logger.warning(f"No news found for paper: {title}")
    except Exception as e:
        logger.error(f"Error getting news information: {e}")
        return None

    # Save the paper news information
    if report_file:
        base_name = os.path.basename(report_file).replace('.json', '')
    else:
        base_name = title.replace(' ', '_')[:50]  # Limit filename length

    news_file = os.path.join(result_dir, f"{base_name}_news.json")
    with open(news_file, 'w', encoding='utf-8') as f:
        json.dump(news_info, f, ensure_ascii=False, indent=2)

    logger.info(f"Paper news information saved to {news_file}")

    # Display the news
    if news_info and news_info.get('news'):
        logger.info("Paper News:")
        logger.info(f"Title: {news_info.get('news')}")
        logger.info(f"Date: {news_info.get('date')}")
        logger.info(f"Description: {news_info.get('description')}")
        logger.info(f"URL: {news_info.get('url')}")

    return news_info

def process_all_reports(input_dir='tests/scholar_tests/results', output_dir='tests/scholar_tests/results'):
    """Process all report files in the input directory."""
    # Find all report files
    report_files = glob.glob(os.path.join(input_dir, '*.json'))

    logger.info(f"Found {len(report_files)} report files in {input_dir}")

    results = []
    for file in tqdm(report_files, desc="Processing reports"):
        result = test_paper_news(report_file=file, output_dir=output_dir)
        if result:
            results.append(file)

    logger.info(f"Processed {len(results)} report files successfully out of {len(report_files)} total")
    return results

def test_specific_papers(output_dir='tests/scholar_tests/results'):
    """Test with specific paper titles."""
    paper_titles = [
        "Attention is All You Need",
        "Sora: A Review on Background, Technology, Limitations, and Opportunities of Large Vision Models",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "Deep Residual Learning for Image Recognition"
    ]

    logger.info(f"Testing {len(paper_titles)} specific paper titles")

    results = []
    for title in tqdm(paper_titles, desc="Processing papers"):
        result = test_paper_news(paper_title=title, output_dir=output_dir)
        if result:
            results.append(title)

    logger.info(f"Processed {len(results)} paper titles successfully out of {len(paper_titles)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test paper news information generation')
    parser.add_argument('--file', type=str, help='Path to scholar report JSON file')
    parser.add_argument('--title', type=str, help='Paper title to get news for')
    parser.add_argument('--input-dir', type=str, default='tests/scholar_tests/results', help='Directory with report files')
    parser.add_argument('--output-dir', type=str, default='tests/scholar_tests/results', help='Directory to save output')
    parser.add_argument('--mode', type=str, choices=['file', 'title', 'batch', 'specific'], default='specific',
                        help='Test mode: file (single file), title (single title), batch (all files), specific (predefined titles)')

    args = parser.parse_args()

    if args.mode == 'file' and args.file:
        test_paper_news(report_file=args.file, output_dir=args.output_dir)
    elif args.mode == 'title' and args.title:
        test_paper_news(paper_title=args.title, output_dir=args.output_dir)
    elif args.mode == 'batch':
        process_all_reports(args.input_dir, args.output_dir)
    else:  # default to 'specific'
        test_specific_papers(args.output_dir)

if __name__ == "__main__":
    main()
