#!/usr/bin/env python
# coding: UTF-8
"""
Test script for career level information generation in the scholar service.
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
from account.juris_people import three_card_juris_people

def test_career_level_info(report_file, output_dir='reports/tests/career_level'):
    """
    Test the career level information generation functionality.
    
    Args:
        report_file (str): Path to the scholar report JSON file
        output_dir (str): Directory to save the output
    
    Returns:
        dict: Career level information if successful, None otherwise
    """
    print(f"Testing career level information generation for {report_file}...")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the report
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        print(f"Error loading report: {e}")
        return None
    
    # Check if the report has publication statistics
    pub_stats = report.get('publication_stats', {})
    if not pub_stats or pub_stats.get('total_papers', 0) <= 0:
        print("No publication statistics found or no papers available")
        level_info = {
            'level_cn': 'N/A (No papers found)',
            'level_us': 'N/A (No papers found)',
            'earnings': 'N/A',
            'justification': 'Cannot determine career level without publication data'
        }
    else:
        # Generate career level information
        try:
            print("Generating career level information...")
            level_info = three_card_juris_people(report)
            if not level_info:  # If level_info is None or empty dictionary
                level_info = {}
            print(f"Career level information generated")
        except Exception as e:
            print(f"Error generating career level information: {e}")
            level_info = {
                'level_cn': 'N/A (Error)',
                'level_us': 'N/A (Error)',
                'earnings': 'N/A',
                'justification': f'Error: {str(e)}'
            }
    
    # Save the career level information
    base_name = os.path.basename(report_file).replace('.json', '')
    level_info_file = os.path.join(output_dir, f"{base_name}_level_info.json")
    with open(level_info_file, 'w', encoding='utf-8') as f:
        json.dump(level_info, f, ensure_ascii=False, indent=2)
    
    print(f"Career level information saved to {level_info_file}")
    
    return level_info

def process_all_reports(input_dir='reports/tests', output_dir='reports/tests/career_level'):
    """Process all report files in the input directory."""
    # Find all report files
    report_files = glob.glob(os.path.join(input_dir, '*.json'))
    
    results = []
    for file in tqdm(report_files, desc="Processing reports"):
        result = test_career_level_info(file, output_dir)
        if result:
            results.append(file)
    
    print(f"\nProcessed {len(results)} report files successfully out of {len(report_files)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test career level information generation')
    parser.add_argument('--file', type=str, help='Path to scholar report JSON file')
    parser.add_argument('--input-dir', type=str, default='reports/tests', help='Directory with report files')
    parser.add_argument('--output-dir', type=str, default='reports/tests/career_level', help='Directory to save output')
    
    args = parser.parse_args()
    
    if args.file:
        test_career_level_info(args.file, args.output_dir)
    else:
        process_all_reports(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()
