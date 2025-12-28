#!/usr/bin/env python
# coding: UTF-8
"""
Script to run scholar analysis for a single scholar.
This script processes a single scholar and saves the results to reports/tests.
"""

import os
import sys
import re
import json
import argparse

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

def process_scholar(name=None, scholar_id=None, url=None, output_dir=None):
    """Process a single scholar."""
    # If URL is provided, extract scholar ID
    if url and not scholar_id:
        scholar_id = extract_scholar_id(url)
        if not scholar_id:
            print(f"Could not extract scholar ID from URL: {url}")
            return None
    
    if not name and not scholar_id:
        print("Either name or scholar_id must be provided")
        return None
    
    print(f"Processing scholar: {name or ''} (ID: {scholar_id or 'None'})")
    
    # Get Crawlbase API token
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')
    
    # Run the scholar analysis
    report = run_scholar_analysis(
        researcher_name=name,
        scholar_id=scholar_id,
        use_crawlbase=True,
        api_token=api_token,
        use_cache=False
    )
    
    if report:
        # Create output filename
        if name:
            safe_name = name.replace(' ', '_').replace(',', '').replace('.', '')
        else:
            safe_name = "scholar"
        
        base_dir = output_dir or os.path.join('reports', 'tests')
        if scholar_id:
            output_file = os.path.join(base_dir, f"{safe_name}_{scholar_id}.json")
        else:
            output_file = os.path.join(base_dir, f"{safe_name}.json")
        
        # Save the report
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"Report saved to {output_file}")
        return output_file
    else:
        print(f"Failed to generate report for {name or scholar_id}")
        return None

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run scholar analysis for a single scholar')
    parser.add_argument('--name', type=str, help='Researcher name')
    parser.add_argument('--id', type=str, help='Google Scholar ID')
    parser.add_argument('--url', type=str, help='Google Scholar URL')
    parser.add_argument('--output-dir', type=str, default='reports/tests', help='Directory to save output')
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Process the scholar
    process_scholar(args.name, args.id, args.url, output_dir=args.output_dir)

if __name__ == "__main__":
    main()
