#!/usr/bin/env python
# coding: UTF-8
"""
Test script for the Scholar API service with direct Scholar ID input.
"""

from account.filter_scholar import filter_user_input
from server.services.scholar.scholar_service import run_scholar_analysis
import os

def main():
    """
    Test the Scholar API service with direct Scholar ID input.
    """
    # Test with a Google Scholar ID
    scholar_id_input = "Y-ql3zMAAAAJ"  # Daiheng Gao's Scholar ID
    
    # Process the input
    processed_input, is_name = filter_user_input(scholar_id_input)
    
    print(f"Input: {scholar_id_input}")
    print(f"Processed input: {processed_input}")
    print(f"Is name: {is_name}")
    
    # If it's not a name (i.e., it's a Scholar ID), use it directly
    if not is_name:
        print(f"Using Scholar ID directly: {processed_input}")
        
        # Run the analysis with the Scholar ID
        api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
        report = run_scholar_analysis(
            scholar_id=processed_input,
            use_crawlbase=bool(api_token),
            api_token=api_token or None,
            use_cache=True,
            cache_max_age_days=3
        )
        
        # Check if the report was generated
        if report:
            print("\nTest completed successfully!")
            print(f"Researcher name: {report['researcher']['name']}")
            print(f"Affiliation: {report['researcher']['affiliation']}")
            print(f"H-index: {report['researcher']['h_index']}")
        else:
            print("\nTest failed: No report was generated.")
    else:
        print(f"Input is a name, not a Scholar ID.")

if __name__ == "__main__":
    main()
