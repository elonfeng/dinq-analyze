#!/usr/bin/env python
# coding: UTF-8
"""
Test script for Step 7 of the scholar service:
- Find most frequent collaborator details
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
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.config.api_keys import API_KEYS

def test_collaborator_details(coauthor_stats_file, output_dir='reports/tests/step7'):
    """
    Test the most frequent collaborator details functionality.
    
    Args:
        coauthor_stats_file (str): Path to the co-author statistics JSON file
        output_dir (str): Directory to save the output
    
    Returns:
        dict: Most frequent collaborator details if successful, None otherwise
    """
    print(f"Testing most frequent collaborator details for {coauthor_stats_file}...")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the co-author statistics
    try:
        with open(coauthor_stats_file, 'r', encoding='utf-8') as f:
            coauthor_stats = json.load(f)
    except Exception as e:
        print(f"Error loading co-author statistics: {e}")
        return None
    
    # Get Crawlbase API token
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')
    
    # Initialize the data fetcher
    data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)
    
    # Find most frequent collaborator details
    most_frequent_collaborator = None
    if coauthor_stats and 'top_coauthors' in coauthor_stats and coauthor_stats['top_coauthors']:
        try:
            top_coauthor = coauthor_stats['top_coauthors'][0]
            coauthor_name = top_coauthor['name']
            best_paper_title = top_coauthor.get('best_paper', {}).get('title', '')
            
            # Search for this coauthor on Google Scholar using the best paper title to get full name
            coauthor_search_results = data_fetcher.search_author_by_name(coauthor_name, paper_title=best_paper_title)
            
            if coauthor_search_results:
                # Get the first result (most relevant)
                coauthor_id = coauthor_search_results[0]['scholar_id']
                coauthor_details = data_fetcher.get_author_details_by_id(coauthor_id)
                
                if coauthor_details:
                    most_frequent_collaborator = {
                        'full_name': coauthor_details.get('full_name', coauthor_name),
                        'affiliation': coauthor_details.get('affiliation', 'Unknown'),
                        'research_interests': coauthor_details.get('research_interests', []),
                        'scholar_id': coauthor_id,
                        'coauthored_papers': top_coauthor['coauthored_papers'],
                        'best_paper': top_coauthor['best_paper'],
                        'h_index': coauthor_details.get('h_index', 'N/A'),
                        'total_citations': coauthor_details.get('total_citations', 'N/A')
                    }
        except Exception as e:
            print(f"Error finding most frequent collaborator: {e}")
            most_frequent_collaborator = None
    
    # If no most frequent collaborator found, create an empty one
    if most_frequent_collaborator is None:
        print("No most frequent collaborator found or error occurred. Creating empty collaborator object.")
        most_frequent_collaborator = {
            'full_name': 'No frequent collaborator found',
            'affiliation': 'N/A',
            'research_interests': [],
            'scholar_id': '',
            'coauthored_papers': 0,
            'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0},
            'h_index': 'N/A',
            'total_citations': 'N/A'
        }
    
    # Save the most frequent collaborator details
    base_name = os.path.basename(coauthor_stats_file).replace('_coauthor_stats.json', '')
    collaborator_file = os.path.join(output_dir, f"{base_name}_collaborator.json")
    with open(collaborator_file, 'w', encoding='utf-8') as f:
        json.dump(most_frequent_collaborator, f, ensure_ascii=False, indent=2)
    
    print(f"Most frequent collaborator details saved to {collaborator_file}")
    
    return most_frequent_collaborator

def process_all_coauthor_stats(input_dir='reports/tests/step4_5', output_dir='reports/tests/step7'):
    """Process all co-author statistics files in the input directory."""
    # Find all co-author statistics files
    coauthor_stats_files = glob.glob(os.path.join(input_dir, '*_coauthor_stats.json'))
    
    results = []
    for file in tqdm(coauthor_stats_files, desc="Processing co-author statistics"):
        result = test_collaborator_details(file, output_dir)
        if result:
            results.append(file)
    
    print(f"\nProcessed {len(results)} co-author statistics files successfully out of {len(coauthor_stats_files)} total")
    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test most frequent collaborator details')
    parser.add_argument('--file', type=str, help='Path to co-author statistics JSON file')
    parser.add_argument('--input-dir', type=str, default='reports/tests/step4_5', help='Directory with co-author statistics files')
    parser.add_argument('--output-dir', type=str, default='reports/tests/step7', help='Directory to save output')
    
    args = parser.parse_args()
    
    if args.file:
        test_collaborator_details(args.file, args.output_dir)
    else:
        process_all_coauthor_stats(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()
