#!/usr/bin/env python
# coding: UTF-8
"""
Test script for Step 3 of the scholar service:
- Analyze publications
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
from server.services.scholar.analyzer import ScholarAnalyzer

def test_publication_analysis(author_data_file, output_dir='reports/tests/step3'):
    """
    Test the publication analysis functionality.
    
    Args:
        author_data_file (str): Path to the author data JSON file
        output_dir (str): Directory to save the output
    
    Returns:
        dict: Publication statistics if successful, None otherwise
    """
    print(f"Testing publication analysis for {author_data_file}...")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the author data
    try:
        with open(author_data_file, 'r', encoding='utf-8') as f:
            author_data = json.load(f)
    except Exception as e:
        print(f"Error loading author data: {e}")
        return None
    
    # Initialize the analyzer
    analyzer = ScholarAnalyzer()
    
    # Analyze publications
    pub_stats = analyzer.analyze_publications(author_data)
    if not pub_stats:
        print("Error: Could not analyze publications")
        return None
    
    # Save the publication statistics
    base_name = os.path.basename(author_data_file).replace('_author_data.json', '')
    pub_stats_file = os.path.join(output_dir, f"{base_name}_pub_stats.json")
    with open(pub_stats_file, 'w', encoding='utf-8') as f:
        json.dump(pub_stats, f, ensure_ascii=False, indent=2)
    
    print(f"Publication statistics saved to {pub_stats_file}")
    
    return pub_stats

def process_all_author_data(input_dir='reports/tests/step1_2', output_dir='reports/tests/step3'):
    """Process all author data files in the input directory."""
    # Find all author data files
    author_data_files = glob.glob(os.path.join(input_dir, '*_author_data.json'))
    
    results = []
    for file in tqdm(author_data_files, desc="Processing author data"):
        result = test_publication_analysis(file, output_dir)
        if result:
            results.append(file)
    
    print(f"\nProcessed {len(results)} author data files successfully out of {len(author_data_files)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test publication analysis')
    parser.add_argument('--file', type=str, help='Path to author data JSON file')
    parser.add_argument('--input-dir', type=str, default='reports/tests/step1_2', help='Directory with author data files')
    parser.add_argument('--output-dir', type=str, default='reports/tests/step3', help='Directory to save output')
    
    args = parser.parse_args()
    
    if args.file:
        test_publication_analysis(args.file, args.output_dir)
    else:
        process_all_author_data(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()
