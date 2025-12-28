#!/usr/bin/env python
# coding: UTF-8
"""
Test script for checking best collaborator functionality with mock data.
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.analyzer import ScholarAnalyzer
from server.utils.conference_matcher import ConferenceMatcher

def create_mock_author_data():
    """
    Create mock author data for testing.
    
    Returns:
        dict: Mock author data
    """
    return {
        "name": "Test Researcher",
        "abbreviated_name": "T. Researcher",
        "affiliation": "Test University",
        "email": "test@example.com",
        "research_fields": ["Computer Vision", "Machine Learning", "Artificial Intelligence"],
        "total_citations": 5000,
        "h_index": 30,
        "papers": [
            {
                "title": "A Novel Approach to CVPR Computer Vision",
                "year": "2023",
                "venue": "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition",
                "citations": 100,
                "authors": ["Test Researcher", "Collaborator One", "Collaborator Two"]
            },
            {
                "title": "Advances in NeurIPS Neural Networks",
                "year": "2022",
                "venue": "Advances in Neural Information Processing Systems",
                "citations": 50,
                "authors": ["Collaborator One", "Test Researcher"]
            },
            {
                "title": "ICLR Paper on Deep Learning",
                "year": "2021",
                "venue": "International Conference on Learning Representations",
                "citations": 200,
                "authors": ["Collaborator Two", "Test Researcher", "Collaborator Three"]
            },
            {
                "title": "Another CVPR Paper",
                "year": "2020",
                "venue": "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition",
                "citations": 300,
                "authors": ["Collaborator Three", "Test Researcher", "Collaborator One"]
            },
            {
                "title": "ECCV Paper on Computer Vision",
                "year": "2020",
                "venue": "European Conference on Computer Vision",
                "citations": 150,
                "authors": ["Test Researcher", "Collaborator Three"]
            }
        ]
    }

def test_best_collaborator(output_dir='tests/scholar_tests/results'):
    """
    Test the best collaborator functionality with mock data.
    
    Args:
        output_dir (str): Directory to save the output
    """
    print("Testing best collaborator with mock data...")
    
    # Ensure output directory exists
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join(output_dir, f"best_collaborator_mock_{timestamp}")
    os.makedirs(result_dir, exist_ok=True)
    
    # Create mock author data
    author_data = create_mock_author_data()
    
    # Save the mock author data
    mock_data_file = os.path.join(result_dir, "mock_author_data.json")
    with open(mock_data_file, 'w', encoding='utf-8') as f:
        json.dump(author_data, f, ensure_ascii=False, indent=2)
    print(f"Mock author data saved to {mock_data_file}")
    
    # Initialize the analyzer
    analyzer = ScholarAnalyzer()
    
    # Analyze co-authors
    coauthor_stats = analyzer.analyze_coauthors(author_data)
    if not coauthor_stats:
        print("Error: Could not analyze co-authors")
        return
    
    # Save the co-author statistics
    coauthor_stats_file = os.path.join(result_dir, "coauthor_stats.json")
    with open(coauthor_stats_file, 'w', encoding='utf-8') as f:
        json.dump(coauthor_stats, f, ensure_ascii=False, indent=2)
    print(f"Co-author statistics saved to {coauthor_stats_file}")
    
    # Extract and display best collaborator information
    top_coauthors = coauthor_stats.get('top_coauthors', [])
    if not top_coauthors:
        print("No top co-authors found.")
        return
    
    # Get the best collaborator (first in the list)
    best_collaborator = top_coauthors[0]
    collaborator_name = best_collaborator.get('name', 'Unknown')
    coauthored_papers = best_collaborator.get('coauthored_papers', 0)
    
    # Extract best paper information
    best_paper = best_collaborator.get('best_paper', {})
    paper_title = best_paper.get('title', 'Unknown')
    paper_year = best_paper.get('year', 'Unknown')
    paper_venue = best_paper.get('venue', 'Unknown')
    paper_original_venue = best_paper.get('original_venue', paper_venue)
    paper_citations = best_paper.get('citations', 0)
    
    # Display the information
    print("\nBest Collaborator Information:")
    print(f"Name: {collaborator_name}")
    print(f"Co-authored Papers: {coauthored_papers}")
    print("\nBest Co-authored Paper:")
    print(f"Title: {paper_title}")
    print(f"Year: {paper_year}")
    print(f"Original Venue: {paper_original_venue}")
    print(f"Venue: {paper_venue}")
    print(f"Citations: {paper_citations}")
    
    # Save the best collaborator information
    collaborator_info = {
        "collaborator_name": collaborator_name,
        "coauthored_papers": coauthored_papers,
        "best_paper": {
            "title": paper_title,
            "year": paper_year,
            "original_venue": paper_original_venue,
            "venue": paper_venue,
            "citations": paper_citations
        }
    }
    
    collaborator_file = os.path.join(result_dir, "best_collaborator.json")
    with open(collaborator_file, 'w', encoding='utf-8') as f:
        json.dump(collaborator_info, f, ensure_ascii=False, indent=2)
    print(f"\nBest collaborator information saved to {collaborator_file}")
    
    # Display all top co-authors
    print("\nAll Top Co-authors:")
    for i, coauthor in enumerate(top_coauthors, 1):
        name = coauthor.get('name', 'Unknown')
        papers = coauthor.get('coauthored_papers', 0)
        best_paper = coauthor.get('best_paper', {})
        paper_title = best_paper.get('title', 'Unknown')
        paper_venue = best_paper.get('venue', 'Unknown')
        paper_citations = best_paper.get('citations', 0)
        
        print(f"{i}. {name} - {papers} papers")
        print(f"   Best Paper: {paper_title}")
        print(f"   Venue: {paper_venue}")
        print(f"   Citations: {paper_citations}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test best collaborator functionality with mock data')
    parser.add_argument('--output-dir', type=str, default='tests/scholar_tests/results', help='Directory to save output')
    
    args = parser.parse_args()
    
    test_best_collaborator(args.output_dir)

if __name__ == "__main__":
    main()
