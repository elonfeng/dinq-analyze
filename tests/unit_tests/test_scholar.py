#!/usr/bin/env python
# coding: UTF-8
"""
Test script for the Scholar API service.
"""

from server.services.scholar.scholar_service import run_scholar_analysis
import os

def main():
    """
    Run a test analysis for a researcher.
    """
    # Test with Daiheng Gao
    researcher_name = "Daiheng Gao"
    
    # Run the analysis
    api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
    report = run_scholar_analysis(
        researcher_name=researcher_name,
        use_crawlbase=bool(api_token),
        api_token=api_token or None,
        use_cache=True,  # Enable cache
        cache_max_age_days=3  # Cache valid for 3 days
    )
    
    # Check if the report was generated
    if report:
        print("\nTest completed successfully!")
        
        # Check if most_frequent_collaborator is in the report
        if 'most_frequent_collaborator' in report and report['most_frequent_collaborator']:
            collab = report['most_frequent_collaborator']
            print(f"\nMost frequent collaborator: {collab.get('full_name', 'Unknown')}")
            print(f"Affiliation: {collab.get('affiliation', 'Unknown')}")
            print(f"Best paper: {collab.get('best_paper', {}).get('title', 'Unknown')}")
        else:
            print("\nNo most frequent collaborator found in the report.")
    else:
        print("\nTest failed: No report was generated.")

if __name__ == "__main__":
    main()
