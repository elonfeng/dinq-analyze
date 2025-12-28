#!/usr/bin/env python
# coding: UTF-8
"""
Extract collaborator information from full scholar data files
- Reads scholar IDs from a file
- Extracts best collaborator information from full scholar data files
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

def find_scholar_data_file(scholar_id):
    """
    Find the full scholar data file.
    
    Args:
        scholar_id (str): Google Scholar ID
        
    Returns:
        str: Path to the scholar data file or None if not found
    """
    # Check in reports/tests directory
    potential_paths = [
        os.path.join('reports', 'tests', f'scholar_{scholar_id}.json'),
        os.path.join('reports', 'tests', 'steps', f'scholar_{scholar_id}_step7_collaborator.json'),
        os.path.join('reports', 'tests', 'step7_fixed_test', f'scholar_{scholar_id}_step4_collaborator.json')
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            return path
    
    # If not found, search for it
    for root, dirs, files in os.walk('reports'):
        for file in files:
            if file.startswith(f'scholar_{scholar_id}') and file.endswith('.json'):
                return os.path.join(root, file)
    
    return None

def extract_collaborator_info(scholar_id, scholar_name, output_dir):
    """
    Extract collaborator information for a scholar.
    
    Args:
        scholar_id (str): Google Scholar ID
        scholar_name (str): Scholar name (for display purposes)
        output_dir (str): Directory to save output files
        
    Returns:
        dict: Best collaborator details or None if error
    """
    print(f"\n{'='*80}")
    print(f"Processing scholar: {scholar_name} (ID: {scholar_id})")
    print(f"{'='*80}")
    
    try:
        # Find scholar data file
        data_file = find_scholar_data_file(scholar_id)
        if not data_file:
            print(f"Scholar data file not found for {scholar_id}")
            return None
        
        print(f"Found scholar data file: {data_file}")
        
        # Load scholar data
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract collaborator information
        collaborator_info = None
        
        # Check if it's a full scholar data file
        if 'most_frequent_collaborator' in data:
            collab = data['most_frequent_collaborator']
            collaborator_info = {
                'full_name': collab.get('full_name', 'Unknown'),
                'affiliation': collab.get('affiliation', 'Unknown'),
                'research_interests': collab.get('research_interests', []),
                'scholar_id': collab.get('scholar_id', ''),
                'coauthored_papers': collab.get('coauthored_papers', 0),
                'best_paper': collab.get('best_paper', {
                    'title': 'N/A',
                    'year': 'N/A',
                    'venue': 'N/A',
                    'citations': 0
                }),
                'h_index': collab.get('h_index', 'N/A'),
                'total_citations': collab.get('total_citations', 'N/A')
            }
        # Check if it's a step7 collaborator file
        elif 'full_name' in data and 'coauthored_papers' in data:
            collaborator_info = {
                'full_name': data.get('full_name', 'Unknown'),
                'affiliation': data.get('affiliation', 'Unknown'),
                'research_interests': data.get('research_interests', []),
                'scholar_id': data.get('scholar_id', ''),
                'coauthored_papers': data.get('coauthored_papers', 0),
                'best_paper': data.get('best_paper', {
                    'title': 'N/A',
                    'year': 'N/A',
                    'venue': 'N/A',
                    'citations': 0
                }),
                'h_index': data.get('h_index', 'N/A'),
                'total_citations': data.get('total_citations', 'N/A')
            }
        # Check if it's a coauthor_stats file
        elif 'coauthor_stats' in data and 'top_coauthors' in data['coauthor_stats'] and data['coauthor_stats']['top_coauthors']:
            top_coauthor = data['coauthor_stats']['top_coauthors'][0]
            collaborator_info = {
                'full_name': top_coauthor.get('name', 'Unknown'),
                'affiliation': 'Unknown',
                'research_interests': [],
                'scholar_id': '',
                'coauthored_papers': top_coauthor.get('coauthored_papers', 0),
                'best_paper': top_coauthor.get('best_paper', {
                    'title': 'N/A',
                    'year': 'N/A',
                    'venue': 'N/A',
                    'citations': 0
                }),
                'h_index': 'N/A',
                'total_citations': 'N/A'
            }
        
        if collaborator_info:
            # Save to file
            output_file = os.path.join(output_dir, f"scholar_{scholar_id}_collaborator.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(collaborator_info, f, ensure_ascii=False, indent=2)
            
            print(f"Collaborator details saved to {output_file}")
        else:
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
        collaborator = extract_collaborator_info(scholar_id, scholar_name, output_dir)
        
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
