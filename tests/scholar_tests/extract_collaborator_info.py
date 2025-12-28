#!/usr/bin/env python
# coding: UTF-8
"""
Extract collaborator information from scholar analysis results
- Reads scholar IDs from a file
- Extracts best collaborator information from scholar analysis results
- Saves results to a single output file
"""

import os
import sys
import json
import time
import argparse
import re
from tqdm import tqdm
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.config.api_keys import API_KEYS

def extract_scholar_id(url):
    """
    Extract Google Scholar ID from a URL.
    
    Args:
        url (str): Google Scholar URL
        
    Returns:
        str: Scholar ID or None if not found
    """
    match = re.search(r'user=([^&]+)', url)
    if match:
        return match.group(1)
    return None

def get_scholar_cache_path(scholar_id):
    """
    Get the path to the scholar cache file.
    
    Args:
        scholar_id (str): Google Scholar ID
        
    Returns:
        str: Path to the scholar cache file
    """
    cache_dir = os.path.join('server', 'cache', 'scholar')
    return os.path.join(cache_dir, f"scholar_{scholar_id}.json")

def extract_collaborator_info(scholar_id, scholar_name, api_token, output_dir):
    """
    Extract collaborator information for a scholar.
    
    Args:
        scholar_id (str): Google Scholar ID
        scholar_name (str): Scholar name (for display purposes)
        api_token (str): Crawlbase API token
        output_dir (str): Directory to save output files
        
    Returns:
        dict: Best collaborator details or None if error
    """
    print(f"\n{'='*80}")
    print(f"Processing scholar: {scholar_name} (ID: {scholar_id})")
    print(f"{'='*80}")
    
    try:
        # Check if scholar cache exists
        cache_file = get_scholar_cache_path(scholar_id)
        if not os.path.exists(cache_file):
            print(f"Scholar cache not found at {cache_file}")
            return None
        
        # Load scholar data from cache
        with open(cache_file, 'r', encoding='utf-8') as f:
            scholar_data = json.load(f)
        
        # Extract most frequent collaborator information
        collaborator_info = None
        if 'most_frequent_collaborator' in scholar_data:
            collab = scholar_data['most_frequent_collaborator']
            collaborator_info = {
                'name': collab.get('name', 'Unknown'),
                'affiliation': collab.get('affiliation', 'Unknown'),
                'number_of_collaborations': collab.get('collaborations', 0),
                'research_interests': []
            }
            
            # Initialize ScholarDataFetcher to get more details
            data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)
            
            # Search for collaborator by name
            print(f"Searching for collaborator: {collaborator_info['name']}...")
            search_results = data_fetcher.search_author_by_name_new(collaborator_info['name'])
            
            if search_results and len(search_results) > 0:
                # Get the first result
                collaborator_id = search_results[0]['scholar_id']
                print(f"Found collaborator ID: {collaborator_id}")
                
                # Get detailed information
                details = data_fetcher.get_author_details_by_id(collaborator_id)
                if details:
                    collaborator_info['scholar_id'] = collaborator_id
                    collaborator_info['full_name'] = details.get('full_name', collaborator_info['name'])
                    collaborator_info['affiliation'] = details.get('affiliation', collaborator_info['affiliation'])
                    collaborator_info['research_interests'] = details.get('research_interests', [])
                    
                    # Save to file
                    output_file = os.path.join(output_dir, f"scholar_{scholar_id}_collaborator.json")
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(collaborator_info, f, ensure_ascii=False, indent=2)
                    
                    print(f"Collaborator details saved to {output_file}")
                    
        
        if not collaborator_info:
            print(f"No collaborator information found for {scholar_name}")
            
        return collaborator_info
        
    except Exception as e:
        print(f"Error extracting collaborator info for {scholar_name}: {e}")
        return None

def batch_extract_collaborators(input_file, output_dir='reports/tests/batch_collaborators', output_file=None):
    """
    Extract collaborator information for multiple scholars.
    
    Args:
        input_file (str): Path to file with scholar URLs/IDs
        output_dir (str): Directory to save individual output files
        output_file (str): Path to save combined results
        
    Returns:
        dict: Combined results for all scholars
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Get Crawlbase API token
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')
    
    # Read scholar list from file
    with open(input_file, 'r', encoding='utf-8') as f:
        scholar_lines = f.readlines()
    
    # Process each scholar
    results = {}
    successful = 0
    failed = 0
    
    for line in tqdm(scholar_lines, desc="Processing scholars"):
        line = line.strip()
        if not line:
            continue
            
        # Parse line (expected format: "Name, URL")
        parts = line.split(',', 1)
        scholar_name = parts[0].strip()
        
        if len(parts) > 1:
            url = parts[1].strip()
            scholar_id = extract_scholar_id(url)
        else:
            # If only one part, assume it's a URL
            url = scholar_name
            scholar_id = extract_scholar_id(url)
            scholar_name = f"Scholar {scholar_id}"
        
        if not scholar_id:
            print(f"Error: Could not extract Scholar ID from {line}")
            failed += 1
            continue
        
        # Extract collaborator information
        collaborator = extract_collaborator_info(scholar_id, scholar_name, api_token, output_dir)
        
        if collaborator:
            # Add to results
            results[scholar_id] = {
                'scholar_name': scholar_name,
                'scholar_id': scholar_id,
                'best_collaborator': collaborator
            }
            successful += 1
        else:
            failed += 1
    
    # Generate summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_scholars': len(scholar_lines),
        'successful': successful,
        'failed': failed,
        'results': results
    }
    
    # Save combined results
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f"batch_collaborators_{timestamp}.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\nBatch processing complete:")
    print(f"- Total scholars: {len(scholar_lines)}")
    print(f"- Successfully processed: {successful}")
    print(f"- Failed: {failed}")
    print(f"- Results saved to: {output_file}")
    
    return summary

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Extract collaborator information for multiple scholars')
    parser.add_argument('--input-file', type=str, default='tests/scholar_tests/0416测试.txt', 
                        help='Path to file with scholar URLs')
    parser.add_argument('--output-dir', type=str, default='reports/tests/batch_collaborators', 
                        help='Directory to save individual output files')
    parser.add_argument('--output-file', type=str, 
                        help='Path to save combined results (default: auto-generated)')
    
    args = parser.parse_args()
    
    batch_extract_collaborators(args.input_file, args.output_dir, args.output_file)

if __name__ == "__main__":
    main()
