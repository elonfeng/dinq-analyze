#!/usr/bin/env python
# coding: UTF-8
"""
Script to run scholar analysis for all scholars in the test file.
This script processes each scholar in the 0416测试.txt file and saves the results to reports/tests.
"""

import os
import sys
import re
import json
from tqdm import tqdm

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the scholar service
from server.services.scholar.scholar_service import run_scholar_analysis
from server.config.api_keys import API_KEYS

def extract_scholar_id(url):
    """Extract scholar ID from Google Scholar URL."""
    match = re.search(r'user=([^&]+)', url)
    if match:
        return match.group(1)
    return None

def process_scholar(line):
    """Process a single scholar line from the test file."""
    parts = line.strip().split(', ', 1)
    
    if len(parts) != 2:
        print(f"Invalid line format: {line}")
        return None
    
    name = parts[0]
    url = parts[1]
    scholar_id = extract_scholar_id(url)
    
    if not scholar_id:
        print(f"Could not extract scholar ID from URL: {url}")
        return None
    
    print(f"Processing scholar: {name} (ID: {scholar_id})")
    
    # Get Crawlbase API token
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')
    
    # Run the scholar analysis
    report = run_scholar_analysis(
        researcher_name=name,
        scholar_id=scholar_id,
        use_crawlbase=True,
        api_token=api_token,
        use_cache=True
    )
    
    if report:
        # Create output filename
        safe_name = name.replace(' ', '_').replace(',', '').replace('.', '')
        output_file = os.path.join('reports', 'tests', f"{safe_name}_{scholar_id}.json")
        
        # Save the report
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"Report saved to {output_file}")
        return output_file
    else:
        print(f"Failed to generate report for {name}")
        return None

def main():
    """Main function to process all scholars in the test file."""
    # Ensure output directory exists
    os.makedirs(os.path.join('reports', 'tests'), exist_ok=True)
    
    # Read the test file
    test_file = os.path.join('tests', 'scholar_tests', '0416测试.txt')
    
    with open(test_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Process each scholar
    results = []
    for line in tqdm(lines, desc="Processing scholars"):
        result = process_scholar(line)
        if result:
            results.append(result)
    
    # Print summary
    print(f"\nProcessed {len(results)} scholars successfully out of {len(lines)} total")
    print(f"Reports saved to reports/tests directory")

if __name__ == "__main__":
    main()
