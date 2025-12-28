#!/usr/bin/env python
# coding: UTF-8
"""
Test script for Steps 4 and 5 of the scholar service using batch processing:
- Step 4: Analyze co-authors
- Step 5: Generate co-author network

This script processes scholars from the 0416测试.txt file and saves results in the tests directory.
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime
from tqdm import tqdm

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.analyzer import ScholarAnalyzer
from server.services.scholar.scholar_service import ScholarService
from server.utils.conference_matcher import ConferenceMatcher

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'coauthor_analysis_batch.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('coauthor_analysis_batch')

def read_scholars_from_file(file_path):
    """
    Read scholar information from the specified file.

    Args:
        file_path (str): Path to the file containing scholar information

    Returns:
        list: List of dictionaries with scholar information
    """
    scholars = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split(', ')
            name = parts[0]
            url = parts[1] if len(parts) > 1 else None

            if url and 'citations?user=' in url:
                # Extract scholar_id from URL
                scholar_id = url.split('user=')[1].split('&')[0]
                scholars.append({
                    'name': name,
                    'url': url,
                    'scholar_id': scholar_id
                })
            else:
                logger.warning(f"Could not extract scholar ID from line: {line}")

        logger.info(f"Read {len(scholars)} scholars from {file_path}")
        return scholars
    except Exception as e:
        logger.error(f"Error reading scholars from file: {e}")
        return []

def test_coauthor_analysis(author_data, output_dir, scholar_info=None):
    """
    Test the co-author analysis and network generation functionality.

    Args:
        author_data (dict): Author data dictionary
        output_dir (str): Directory to save the output
        scholar_info (dict, optional): Additional scholar information

    Returns:
        tuple: (coauthor_stats, coauthor_network) if successful, None otherwise
    """
    if not author_data:
        logger.error("No author data provided")
        return None

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Get scholar name and ID
    scholar_name = scholar_info.get('name') if scholar_info else author_data.get('name', 'unknown')
    scholar_id = scholar_info.get('scholar_id') if scholar_info else author_data.get('scholar_id', 'unknown')

    logger.info(f"Testing co-author analysis for {scholar_name} (ID: {scholar_id})...")

    # Initialize the analyzer
    analyzer = ScholarAnalyzer()

    # Step 4: Analyze co-authors
    coauthor_stats = analyzer.analyze_coauthors(author_data)
    if not coauthor_stats:
        logger.error(f"Could not analyze co-authors for {scholar_name}")
        return None

    # Save the co-author statistics
    filename_base = f"{scholar_id}_{scholar_name.replace(' ', '_')}"
    coauthor_stats_file = os.path.join(output_dir, f"{filename_base}_coauthor_stats.json")

    with open(coauthor_stats_file, 'w', encoding='utf-8') as f:
        json.dump(coauthor_stats, f, ensure_ascii=False, indent=2)

    logger.info(f"Co-author statistics saved to {coauthor_stats_file}")

    # Step 5: Generate co-author network
    coauthor_network = analyzer.generate_coauthor_network(author_data)
    if not coauthor_network:
        logger.error(f"Could not generate co-author network for {scholar_name}")
        return coauthor_stats, None

    # Save the co-author network
    coauthor_network_file = os.path.join(output_dir, f"{filename_base}_coauthor_network.json")

    # Convert NetworkX graph to JSON serializable format
    network_data = {
        'nodes': list(coauthor_network.nodes()),
        'edges': list(coauthor_network.edges())
    }

    with open(coauthor_network_file, 'w', encoding='utf-8') as f:
        json.dump(network_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Co-author network saved to {coauthor_network_file}")

    # Save a summary file with key statistics
    summary = {
        'scholar_name': scholar_name,
        'scholar_id': scholar_id,
        'total_papers': len(author_data.get('papers', [])),
        'total_coauthors': coauthor_stats.get('total_coauthors', 0),
        'top_coauthors': [
            {
                'name': coauthor.get('name', ''),
                'papers': coauthor.get('coauthored_papers', 0),
                'best_paper': {
                    'title': coauthor.get('best_paper', {}).get('title', ''),
                    'venue': coauthor.get('best_paper', {}).get('venue', ''),
                    'original_venue': coauthor.get('best_paper', {}).get('original_venue', ''),
                    'year': coauthor.get('best_paper', {}).get('year', ''),
                    'citations': coauthor.get('best_paper', {}).get('citations', 0)
                }
            }
            for coauthor in coauthor_stats.get('top_coauthors', [])[:5]  # Just include top 5
        ]
    }

    summary_file = os.path.join(output_dir, f"{filename_base}_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"Summary saved to {summary_file}")

    return coauthor_stats, coauthor_network

def process_scholars_batch(scholars_file, output_dir):
    """
    Process a batch of scholars from the specified file.

    Args:
        scholars_file (str): Path to the file containing scholar information
        output_dir (str): Directory to save the output

    Returns:
        list: List of successfully processed scholars
    """
    # Read scholars from file
    scholars = read_scholars_from_file(scholars_file)
    if not scholars:
        logger.error("No scholars found in the file")
        return []

    # Initialize the scholar service
    scholar_service = ScholarService()

    # Create timestamp for this batch
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_output_dir = os.path.join(output_dir, f"batch_{timestamp}")
    os.makedirs(batch_output_dir, exist_ok=True)

    # Save the list of scholars being processed
    scholars_list_file = os.path.join(batch_output_dir, "scholars_list.json")
    with open(scholars_list_file, 'w', encoding='utf-8') as f:
        json.dump(scholars, f, ensure_ascii=False, indent=2)

    # Process each scholar
    results = []
    for i, scholar in enumerate(tqdm(scholars, desc="Processing scholars")):
        logger.info(f"Processing scholar {i+1}/{len(scholars)}: {scholar['name']} (ID: {scholar['scholar_id']})")

        try:
            # Get author data from scholar service
            report = scholar_service.generate_report(scholar_id=scholar['scholar_id'])

            # Extract author data from the report
            if not report:
                logger.error(f"Could not generate report for {scholar['name']} (ID: {scholar['scholar_id']})")
                continue

            # The author data is contained in the report
            author_data = {
                'name': report.get('researcher', {}).get('name', scholar['name']),
                'scholar_id': scholar['scholar_id'],
                'papers': report.get('publication_stats', {}).get('papers', [])
            }

            if not author_data:
                logger.error(f"Could not retrieve author data for {scholar['name']} (ID: {scholar['scholar_id']})")
                continue

            # Run co-author analysis
            result = test_coauthor_analysis(author_data, batch_output_dir, scholar)

            if result:
                results.append({
                    'name': scholar['name'],
                    'scholar_id': scholar['scholar_id'],
                    'success': True
                })
            else:
                logger.warning(f"Co-author analysis failed for {scholar['name']} (ID: {scholar['scholar_id']})")
                results.append({
                    'name': scholar['name'],
                    'scholar_id': scholar['scholar_id'],
                    'success': False
                })

            # Sleep to avoid rate limiting
            time.sleep(2)

        except Exception as e:
            logger.error(f"Error processing scholar {scholar['name']} (ID: {scholar['scholar_id']}): {e}")
            results.append({
                'name': scholar['name'],
                'scholar_id': scholar['scholar_id'],
                'success': False,
                'error': str(e)
            })

    # Save the results
    results_file = os.path.join(batch_output_dir, "processing_results.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"Processed {len(results)} scholars, results saved to {results_file}")

    # Generate a summary of the batch processing
    successful = [r for r in results if r.get('success', False)]
    logger.info(f"Successfully processed {len(successful)} out of {len(scholars)} scholars")

    return results

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test co-author analysis and network generation in batch mode')
    parser.add_argument('--scholars-file', type=str, default='tests/scholar_tests/0416测试.txt',
                        help='Path to file with scholar information')
    parser.add_argument('--output-dir', type=str, default='tests/scholar_tests/results',
                        help='Directory to save output')

    args = parser.parse_args()

    process_scholars_batch(args.scholars_file, args.output_dir)

if __name__ == "__main__":
    main()
