#!/usr/bin/env python
# coding: UTF-8
"""
Batch test script for finding best collaborators for multiple scholars
- Reads scholar IDs from a file
- Runs analysis to get coauthor statistics
- Finds best collaborator details for each scholar
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
from server.services.scholar.scholar_service import run_scholar_analysis
from server.config.api_keys import API_KEYS
from tests.scholar_tests.test_step7_collaborator_details import test_collaborator_details

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

def process_scholar(scholar_id, scholar_name, api_token, output_dir):
    """
    Process a single scholar to find their best collaborator.
    
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
        # Step 1: Run scholar analysis to get coauthor statistics
        coauthor_stats_file = os.path.join(output_dir, f"scholar_{scholar_id}_coauthor_stats.json")
        
        # Check if coauthor stats already exist
        if os.path.exists(coauthor_stats_file):
            print(f"Coauthor statistics already exist at {coauthor_stats_file}")
        else:
            print(f"Running scholar analysis for {scholar_name}...")
            # Run scholar analysis with callback to show progress
            def status_callback(message):
                print(f"  {message}")
                
            # Run the analysis
            report = run_scholar_analysis(
                scholar_id=scholar_id,
                use_crawlbase=True,
                api_token=api_token,
                callback=status_callback,
                use_cache=True,
                cache_max_age_days=7
            )
            
            # Check if coauthor stats were generated
            if not os.path.exists(coauthor_stats_file):
                print(f"Error: Coauthor statistics file not generated at {coauthor_stats_file}")
                return None
        
        # Step 2: Find best collaborator details
        print(f"Finding best collaborator details for {scholar_name}...")
        collaborator = test_collaborator_details(coauthor_stats_file, output_dir)
        
        return collaborator
        
    except Exception as e:
        print(f"Error processing scholar {scholar_name}: {e}")
        return None

def batch_process_scholars(input_file, output_dir='reports/tests/batch_collaborators', output_file=None):
    """
    Process multiple scholars from an input file.
    
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
        
        # Process the scholar
        collaborator = process_scholar(scholar_id, scholar_name, api_token, output_dir)
        
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
    parser = argparse.ArgumentParser(description='Batch test for finding best collaborators')
    parser.add_argument('--input-file', type=str, default='tests/scholar_tests/0416测试.txt', 
                        help='Path to file with scholar URLs')
    parser.add_argument('--output-dir', type=str, default='reports/tests/batch_collaborators', 
                        help='Directory to save individual output files')
    parser.add_argument('--output-file', type=str, 
                        help='Path to save combined results (default: auto-generated)')
    
    args = parser.parse_args()
    
    batch_process_scholars(args.input_file, args.output_dir, args.output_file)

if __name__ == "__main__":
    main()
