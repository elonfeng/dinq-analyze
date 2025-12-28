#!/usr/bin/env python
# coding: UTF-8
"""
Test script for checking best collaborator information.
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.scholar_service import ScholarService
from server.utils.conference_matcher import extract_conference_info_with_year

def test_best_collaborator(scholar_id, output_dir='tests/scholar_tests/results'):
    """
    Test the best collaborator functionality for a specific scholar.
    
    Args:
        scholar_id (str): Google Scholar ID
        output_dir (str): Directory to save the output
    """
    print(f"Testing best collaborator for scholar ID: {scholar_id}")
    
    # Ensure output directory exists
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join(output_dir, f"best_collaborator_{timestamp}")
    os.makedirs(result_dir, exist_ok=True)
    
    # Initialize the scholar service
    scholar_service = ScholarService()
    
    # Generate the report
    report = scholar_service.generate_report(scholar_id=scholar_id)
    if not report:
        print(f"Error: Could not generate report for scholar ID: {scholar_id}")
        return
    
    # Save the full report
    report_file = os.path.join(result_dir, f"{scholar_id}_full_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Full report saved to {report_file}")
    
    # Extract and display best collaborator information
    most_frequent_collaborator = report.get('most_frequent_collaborator', {})
    if not most_frequent_collaborator or most_frequent_collaborator.get('full_name') == 'No frequent collaborator found':
        print("No best collaborator found.")
        return
    
    # Extract collaborator information
    collaborator_name = most_frequent_collaborator.get('full_name', 'Unknown')
    collaborator_affiliation = most_frequent_collaborator.get('affiliation', 'Unknown')
    coauthored_papers = most_frequent_collaborator.get('coauthored_papers', 0)
    
    # Extract best paper information
    best_paper = most_frequent_collaborator.get('best_paper', {})
    paper_title = best_paper.get('title', 'Unknown')
    paper_year = best_paper.get('year', 'Unknown')
    paper_venue = best_paper.get('venue', 'Unknown')
    paper_original_venue = best_paper.get('original_venue', paper_venue)
    paper_citations = best_paper.get('citations', 0)
    
    # Use conference matcher to get standardized venue
    matched_venue = extract_conference_info_with_year(paper_venue)
    
    # Display the information
    print("\nBest Collaborator Information:")
    print(f"Name: {collaborator_name}")
    print(f"Affiliation: {collaborator_affiliation}")
    print(f"Co-authored Papers: {coauthored_papers}")
    print("\nBest Co-authored Paper:")
    print(f"Title: {paper_title}")
    print(f"Year: {paper_year}")
    print(f"Original Venue: {paper_original_venue}")
    print(f"Venue: {paper_venue}")
    print(f"Matched Venue: {matched_venue}")
    print(f"Citations: {paper_citations}")
    
    # Save the best collaborator information
    collaborator_info = {
        "collaborator_name": collaborator_name,
        "collaborator_affiliation": collaborator_affiliation,
        "coauthored_papers": coauthored_papers,
        "best_paper": {
            "title": paper_title,
            "year": paper_year,
            "original_venue": paper_original_venue,
            "venue": paper_venue,
            "matched_venue": matched_venue,
            "citations": paper_citations
        }
    }
    
    collaborator_file = os.path.join(result_dir, f"{scholar_id}_best_collaborator.json")
    with open(collaborator_file, 'w', encoding='utf-8') as f:
        json.dump(collaborator_info, f, ensure_ascii=False, indent=2)
    print(f"\nBest collaborator information saved to {collaborator_file}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test best collaborator functionality')
    parser.add_argument('--scholar-id', type=str, default='mG4imMEAAAAJ', help='Google Scholar ID')
    parser.add_argument('--output-dir', type=str, default='tests/scholar_tests/results', help='Directory to save output')
    
    args = parser.parse_args()
    
    test_best_collaborator(args.scholar_id, args.output_dir)

if __name__ == "__main__":
    main()
