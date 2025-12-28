#!/usr/bin/env python
# coding: UTF-8
"""
Test script for Step 6 of the scholar service:
- Calculate researcher rating
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

def test_researcher_rating(author_data_file, pub_stats_file, coauthor_stats_file, output_dir='reports/tests/step6'):
    """
    Test the researcher rating calculation functionality.
    
    Args:
        author_data_file (str): Path to the author data JSON file
        pub_stats_file (str): Path to the publication statistics JSON file
        coauthor_stats_file (str): Path to the co-author statistics JSON file
        output_dir (str): Directory to save the output
    
    Returns:
        dict: Researcher rating if successful, None otherwise
    """
    print(f"Testing researcher rating calculation for {author_data_file}...")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the author data
    try:
        with open(author_data_file, 'r', encoding='utf-8') as f:
            author_data = json.load(f)
    except Exception as e:
        print(f"Error loading author data: {e}")
        return None
    
    # Load the publication statistics
    try:
        with open(pub_stats_file, 'r', encoding='utf-8') as f:
            pub_stats = json.load(f)
    except Exception as e:
        print(f"Error loading publication statistics: {e}")
        return None
    
    # Load the co-author statistics
    try:
        with open(coauthor_stats_file, 'r', encoding='utf-8') as f:
            coauthor_stats = json.load(f)
    except Exception as e:
        print(f"Error loading co-author statistics: {e}")
        return None
    
    # Initialize the analyzer
    analyzer = ScholarAnalyzer()
    
    # Calculate researcher rating
    rating = analyzer.calculate_researcher_rating(author_data, pub_stats, coauthor_stats)
    if not rating:
        print("Error: Could not calculate researcher rating")
        return None
    
    # Save the researcher rating
    base_name = os.path.basename(author_data_file).replace('_author_data.json', '')
    rating_file = os.path.join(output_dir, f"{base_name}_rating.json")
    with open(rating_file, 'w', encoding='utf-8') as f:
        json.dump(rating, f, ensure_ascii=False, indent=2)
    
    print(f"Researcher rating saved to {rating_file}")
    
    return rating

def find_matching_files(base_name, step3_dir, step4_5_dir):
    """Find matching publication and co-author statistics files."""
    pub_stats_file = os.path.join(step3_dir, f"{base_name}_pub_stats.json")
    coauthor_stats_file = os.path.join(step4_5_dir, f"{base_name}_coauthor_stats.json")
    
    if os.path.exists(pub_stats_file) and os.path.exists(coauthor_stats_file):
        return pub_stats_file, coauthor_stats_file
    
    return None, None

def process_all_author_data(input_dir='reports/tests/step1_2', step3_dir='reports/tests/step3', 
                           step4_5_dir='reports/tests/step4_5', output_dir='reports/tests/step6'):
    """Process all author data files in the input directory."""
    # Find all author data files
    author_data_files = glob.glob(os.path.join(input_dir, '*_author_data.json'))
    
    results = []
    for file in tqdm(author_data_files, desc="Processing author data"):
        base_name = os.path.basename(file).replace('_author_data.json', '')
        pub_stats_file, coauthor_stats_file = find_matching_files(base_name, step3_dir, step4_5_dir)
        
        if pub_stats_file and coauthor_stats_file:
            result = test_researcher_rating(file, pub_stats_file, coauthor_stats_file, output_dir)
            if result:
                results.append(file)
        else:
            print(f"Missing publication or co-author statistics for {base_name}")
    
    print(f"\nProcessed {len(results)} author data files successfully out of {len(author_data_files)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test researcher rating calculation')
    parser.add_argument('--author-file', type=str, help='Path to author data JSON file')
    parser.add_argument('--pub-stats-file', type=str, help='Path to publication statistics JSON file')
    parser.add_argument('--coauthor-stats-file', type=str, help='Path to co-author statistics JSON file')
    parser.add_argument('--input-dir', type=str, default='reports/tests/step1_2', help='Directory with author data files')
    parser.add_argument('--step3-dir', type=str, default='reports/tests/step3', help='Directory with publication statistics files')
    parser.add_argument('--step4-5-dir', type=str, default='reports/tests/step4_5', help='Directory with co-author statistics files')
    parser.add_argument('--output-dir', type=str, default='reports/tests/step6', help='Directory to save output')
    
    args = parser.parse_args()
    
    if args.author_file and args.pub_stats_file and args.coauthor_stats_file:
        test_researcher_rating(args.author_file, args.pub_stats_file, args.coauthor_stats_file, args.output_dir)
    else:
        process_all_author_data(args.input_dir, args.step3_dir, args.step4_5_dir, args.output_dir)

if __name__ == "__main__":
    main()
