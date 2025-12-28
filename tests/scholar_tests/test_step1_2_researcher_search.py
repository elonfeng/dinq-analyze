#!/usr/bin/env python
# coding: UTF-8
"""
Test script for Steps 1 and 2 of the scholar service:
- Step 1: Search for the researcher
- Step 2: Get full profile with publications
"""

import os
import sys
import json
import argparse
from tqdm import tqdm

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.config.api_keys import API_KEYS

def test_researcher_search(researcher_name=None, scholar_id=None, output_dir='reports/tests/step1_2'):
    """
    Test the researcher search and profile retrieval functionality.
    
    Args:
        researcher_name (str, optional): Name of the researcher
        scholar_id (str, optional): Google Scholar ID
        output_dir (str): Directory to save the output
    
    Returns:
        dict: Author data if successful, None otherwise
    """
    print(f"Testing researcher search for {'ID: ' + scholar_id if scholar_id else 'Name: ' + researcher_name}...")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Get Crawlbase API token
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')
    
    # Initialize the data fetcher
    data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)
    
    # Step 1: Search for the researcher
    author_info = data_fetcher.search_researcher(name=researcher_name, scholar_id=scholar_id)
    if not author_info:
        print(f"Error: Could not find researcher {'ID: ' + scholar_id if scholar_id else 'Name: ' + researcher_name}")
        return None
    
    # Save the author info
    safe_name = researcher_name.replace(' ', '_').replace(',', '').replace('.', '') if researcher_name else scholar_id
    author_info_file = os.path.join(output_dir, f"{safe_name}_author_info.json")
    with open(author_info_file, 'w', encoding='utf-8') as f:
        json.dump(author_info, f, ensure_ascii=False, indent=2)
    
    print(f"Author info saved to {author_info_file}")
    
    # Step 2: Get full profile with publications
    author_data = data_fetcher.get_full_profile(author_info)
    if not author_data:
        print("Error: Could not retrieve full profile")
        return None
    
    # Save the author data
    author_data_file = os.path.join(output_dir, f"{safe_name}_author_data.json")
    with open(author_data_file, 'w', encoding='utf-8') as f:
        json.dump(author_data, f, ensure_ascii=False, indent=2)
    
    print(f"Author data saved to {author_data_file}")
    
    return author_data

def process_test_file(test_file, output_dir):
    """Process all scholars in the test file."""
    with open(test_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    results = []
    for line in tqdm(lines, desc="Processing scholars"):
        parts = line.strip().split(', ', 1)
        
        if len(parts) != 2:
            print(f"Invalid line format: {line}")
            continue
        
        name = parts[0]
        url = parts[1]
        
        # Extract scholar ID from URL
        import re
        match = re.search(r'user=([^&]+)', url)
        if not match:
            print(f"Could not extract scholar ID from URL: {url}")
            continue
        
        scholar_id = match.group(1)
        
        # Test researcher search
        result = test_researcher_search(name, scholar_id, output_dir)
        if result:
            results.append((name, scholar_id))
    
    print(f"\nProcessed {len(results)} scholars successfully out of {len(lines)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test researcher search and profile retrieval')
    parser.add_argument('--name', type=str, help='Researcher name')
    parser.add_argument('--id', type=str, help='Google Scholar ID')
    parser.add_argument('--test-file', type=str, help='Path to test file with scholar names and URLs')
    parser.add_argument('--output-dir', type=str, default='reports/tests/step1_2', help='Directory to save output')
    
    args = parser.parse_args()
    
    if args.test_file:
        process_test_file(args.test_file, args.output_dir)
    elif args.name or args.id:
        test_researcher_search(args.name, args.id, args.output_dir)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
