#!/usr/bin/env python
# coding: UTF-8
"""
Test script for critical evaluation generation in the scholar service.
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
from server.utils.kimi_evaluator import generate_critical_evaluation

def test_critical_evaluation(report_file, output_dir='reports/tests/critical_evaluation'):
    """
    Test the critical evaluation generation functionality.
    
    Args:
        report_file (str): Path to the scholar report JSON file
        output_dir (str): Directory to save the output
    
    Returns:
        str: Critical evaluation if successful, None otherwise
    """
    print(f"Testing critical evaluation generation for {report_file}...")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the report
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        print(f"Error loading report: {e}")
        return None
    
    # Generate critical evaluation
    try:
        print("Generating critical evaluation...")
        critical_evaluation = generate_critical_evaluation(report)
        print(f"Critical evaluation generated: {critical_evaluation[:50]}...")
    except Exception as e:
        print(f"Error generating critical evaluation: {e}")
        critical_evaluation = "Error generating critical evaluation."
    
    # Save the critical evaluation
    base_name = os.path.basename(report_file).replace('.json', '')
    evaluation_file = os.path.join(output_dir, f"{base_name}_evaluation.txt")
    with open(evaluation_file, 'w', encoding='utf-8') as f:
        f.write(critical_evaluation)
    
    print(f"Critical evaluation saved to {evaluation_file}")
    
    return critical_evaluation

def process_all_reports(input_dir='reports/tests', output_dir='reports/tests/critical_evaluation'):
    """Process all report files in the input directory."""
    # Find all report files
    report_files = glob.glob(os.path.join(input_dir, '*.json'))
    
    results = []
    for file in tqdm(report_files, desc="Processing reports"):
        result = test_critical_evaluation(file, output_dir)
        if result:
            results.append(file)
    
    print(f"\nProcessed {len(results)} report files successfully out of {len(report_files)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test critical evaluation generation')
    parser.add_argument('--file', type=str, help='Path to scholar report JSON file')
    parser.add_argument('--input-dir', type=str, default='reports/tests', help='Directory with report files')
    parser.add_argument('--output-dir', type=str, default='reports/tests/critical_evaluation', help='Directory to save output')
    
    args = parser.parse_args()
    
    if args.file:
        test_critical_evaluation(args.file, args.output_dir)
    else:
        process_all_reports(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()
