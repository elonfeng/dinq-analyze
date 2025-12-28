#!/usr/bin/env python
# coding: UTF-8
"""
Test script to verify that the analyzer uses the years_of_papers field correctly.
"""

import os
import json
from pprint import pprint

# Import the data fetcher and analyzer
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.analyzer import ScholarAnalyzer

def create_sample_profile():
    """
    Create a sample profile with papers from different years.
    """
    sample_papers = [
        {"title": "Paper 1", "year": "2018", "citations": "10", "authors": ["A Author", "B Author"]},
        {"title": "Paper 2", "year": "2019", "citations": "15", "authors": ["A Author", "C Author"]},
        {"title": "Paper 3", "year": "2019", "citations": "5", "authors": ["A Author", "D Author"]},
        {"title": "Paper 4", "year": "2020", "citations": "8", "authors": ["A Author", "E Author"]},
        {"title": "Paper 5", "year": "2021", "citations": "12", "authors": ["A Author", "F Author"]},
        {"title": "Paper 6", "year": "2021", "citations": "9", "authors": ["A Author", "G Author"]},
        {"title": "Paper 7", "year": "2021", "citations": "4", "authors": ["A Author", "H Author"]},
        {"title": "Paper 8", "year": "2022", "citations": "7", "authors": ["A Author", "I Author"]},
        {"title": "Paper 9", "year": "2022", "citations": "3", "authors": ["A Author", "J Author"]},
        {"title": "Paper 10", "year": "2022", "citations": "5", "authors": ["A Author", "K Author"]},
        {"title": "Paper 11", "year": "2022", "citations": "2", "authors": ["A Author", "L Author"]},
        {"title": "Paper 12", "year": "2023", "citations": "6", "authors": ["A Author", "M Author"]},
        {"title": "Paper 13", "year": "2023", "citations": "4", "authors": ["A Author", "N Author"]},
        {"title": "Paper 14", "year": "2023", "citations": "3", "authors": ["A Author", "O Author"]},
        {"title": "Paper 15", "year": "2023", "citations": "1", "authors": ["A Author", "P Author"]},
        {"title": "Paper 16", "year": "2024", "citations": "0", "authors": ["A Author", "Q Author"]},
        {"title": "Paper 17", "year": "2024", "citations": "0", "authors": ["A Author", "R Author"]},
        {"title": "Paper 18", "year": "2024", "citations": "0", "authors": ["A Author", "S Author"]},
        {"title": "Paper 19", "year": "2025", "citations": "0", "authors": ["A Author", "T Author"]},
        {"title": "Paper 20", "year": "2025", "citations": "0", "authors": ["A Author", "U Author"]},
        {"title": "Paper 21", "year": "2025", "citations": "0", "authors": ["A Author", "V Author"]},
        {"title": "Paper 22", "year": "invalid", "citations": "0", "authors": ["A Author", "W Author"]},
    ]
    
    # Create the sample profile
    sample_profile = {
        "name": "Sample Researcher",
        "abbreviated_name": "S. Researcher",
        "affiliation": "Test University",
        "total_citations": 94,
        "papers": sample_papers
    }
    
    # Calculate the year distribution (same as in data_fetcher.py)
    years_of_papers = {}
    for paper in sample_profile.get('papers', []):
        year = paper.get('year', '')
        if year and year.strip() and year.strip().isdigit():
            year = int(year.strip())
            years_of_papers[year] = years_of_papers.get(year, 0) + 1
    
    # Add the calculated years_of_papers to the profile
    sample_profile['years_of_papers'] = years_of_papers
    
    return sample_profile

def test_years_of_papers_usage():
    """
    Test that the analyzer uses the years_of_papers field correctly.
    """
    print("Testing years_of_papers field usage in analyzer...")
    
    # Create a sample profile
    profile = create_sample_profile()
    
    # Print the pre-calculated years_of_papers
    print("\nPre-calculated years_of_papers in profile:")
    pprint(profile.get('years_of_papers', {}))
    
    # Create and use the analyzer
    analyzer = ScholarAnalyzer()
    pub_stats = analyzer.analyze_publications(profile)
    
    # Compare the year_distribution in pub_stats with years_of_papers in profile
    print("\nYear distribution in publication stats:")
    pprint(pub_stats.get('year_distribution', {}))
    
    # Convert both to sorted string representation for comparison
    original_years = str(sorted(profile.get('years_of_papers', {}).items()))
    stats_years = str(sorted(pub_stats.get('year_distribution', {}).items()))
    
    # Check if they match
    if original_years == stats_years:
        print("\nTEST PASSED: Year distributions match")
    else:
        print("\nTEST FAILED: Year distributions do not match")
        print(f"Original: {original_years}")
        print(f"Stats: {stats_years}")
    
    # Save detailed results
    with open("test_results.json", "w") as f:
        json.dump({
            "profile_years_of_papers": profile.get('years_of_papers', {}),
            "pub_stats_year_distribution": pub_stats.get('year_distribution', {}),
            "match": original_years == stats_years
        }, f, indent=4)
    
    print("\nDetailed results saved to test_results.json")

if __name__ == "__main__":
    test_years_of_papers_usage() 
