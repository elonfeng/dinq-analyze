#!/usr/bin/env python
# coding: UTF-8
"""
Test script for arxiv information retrieval in the scholar service.
"""

import os
import sys
import json
import argparse
import glob
from tqdm import tqdm

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.utils.find_arxiv import find_arxiv

def test_arxiv_info(report_file, output_dir='reports/tests/arxiv_info'):
    """
    Test the arxiv information retrieval functionality.
    
    Args:
        report_file (str): Path to the scholar report JSON file
        output_dir (str): Directory to save the output
    
    Returns:
        dict: Arxiv information if successful, None otherwise
    """
    print(f"Testing arxiv information retrieval for {report_file}...")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the report
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        print(f"Error loading report: {e}")
        return None
    
    # Get the most cited paper title
    most_cited_paper = report.get('most_cited_paper', {})
    title = most_cited_paper.get('title', 'Unknown Title')
    
    # Retrieve arxiv information
    try:
        print(f"Finding arxiv information for paper: {title}")
        most_cited_ai_paper = find_arxiv(title)
        print(f"Arxiv information retrieved")
    except Exception as e:
        print(f"Error finding arxiv: {e}")
        most_cited_ai_paper = {"name": title, "arxiv_url": "", "image": ""}
    
    # Save the arxiv information
    base_name = os.path.basename(report_file).replace('.json', '')
    arxiv_file = os.path.join(output_dir, f"{base_name}_arxiv.json")
    with open(arxiv_file, 'w', encoding='utf-8') as f:
        json.dump(most_cited_ai_paper, f, ensure_ascii=False, indent=2)
    
    print(f"Arxiv information saved to {arxiv_file}")
    
    return most_cited_ai_paper

def process_all_reports(input_dir='reports/tests', output_dir='reports/tests/arxiv_info'):
    """Process all report files in the input directory."""
    # Find all report files
    report_files = glob.glob(os.path.join(input_dir, '*.json'))
    
    results = []
    for file in tqdm(report_files, desc="Processing reports"):
        result = test_arxiv_info(file, output_dir)
        if result:
            results.append(file)
    
    print(f"\nProcessed {len(results)} report files successfully out of {len(report_files)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test arxiv information retrieval')
    parser.add_argument('--file', type=str, help='Path to scholar report JSON file')
    parser.add_argument('--input-dir', type=str, default='reports/tests', help='Directory with report files')
    parser.add_argument('--output-dir', type=str, default='reports/tests/arxiv_info', help='Directory to save output')
    
    args = parser.parse_args()
    
    if args.file:
        test_arxiv_info(args.file, args.output_dir)
    else:
        process_all_reports(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()
