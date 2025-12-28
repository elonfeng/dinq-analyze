#!/usr/bin/env python
# coding: UTF-8
"""
Test script for role model information generation in the scholar service.
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
from server.services.scholar.template_figure_kimi import get_template_figure

def test_role_model_info(report_file, output_dir='reports/tests/role_model'):
    """
    Test the role model information generation functionality.
    
    Args:
        report_file (str): Path to the scholar report JSON file
        output_dir (str): Directory to save the output
    
    Returns:
        dict: Role model information if successful, None otherwise
    """
    print(f"Testing role model information generation for {report_file}...")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the report
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        print(f"Error loading report: {e}")
        return None
    
    # Generate role model information
    try:
        print("Generating role model information...")
        role_model = get_template_figure(report)
        print(f"Role model information generated")
    except Exception as e:
        print(f"Error generating role model information: {e}")
        role_model = None
    
    if role_model:
        # Save the role model information
        base_name = os.path.basename(report_file).replace('.json', '')
        role_model_file = os.path.join(output_dir, f"{base_name}_role_model.json")
        with open(role_model_file, 'w', encoding='utf-8') as f:
            json.dump(role_model, f, ensure_ascii=False, indent=2)
        
        print(f"Role model information saved to {role_model_file}")
    
    return role_model

def process_all_reports(input_dir='reports/tests', output_dir='reports/tests/role_model'):
    """Process all report files in the input directory."""
    # Find all report files
    report_files = glob.glob(os.path.join(input_dir, '*.json'))
    
    results = []
    for file in tqdm(report_files, desc="Processing reports"):
        result = test_role_model_info(file, output_dir)
        if result:
            results.append(file)
    
    print(f"\nProcessed {len(results)} report files successfully out of {len(report_files)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test role model information generation')
    parser.add_argument('--file', type=str, help='Path to scholar report JSON file')
    parser.add_argument('--input-dir', type=str, default='reports/tests', help='Directory with report files')
    parser.add_argument('--output-dir', type=str, default='reports/tests/role_model', help='Directory to save output')
    
    args = parser.parse_args()
    
    if args.file:
        test_role_model_info(args.file, args.output_dir)
    else:
        process_all_reports(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()
