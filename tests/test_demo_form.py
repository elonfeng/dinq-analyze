"""
Test script for the demo form API.

This script tests the demo form API endpoint.
"""

import sys
import os
import json
import requests

# Add the project root to the Python path to enable absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Base URL for API requests
BASE_URL = "http://localhost:5002"

def test_get_demo_form_info():
    """Test getting demo form information."""
    print("\n=== Testing Demo Form Info API ===")
    
    # Prepare request
    url = f"{BASE_URL}/api/demo-form/info"
    headers = {
        "Content-Type": "application/json"
    }
    
    # Send request
    print(f"Sending GET request to {url}")
    response = requests.get(url, headers=headers)
    
    # Print response
    print(f"Status code: {response.status_code}")
    
    # Check if successful
    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success', False)}")
        
        # Print form information summary
        form_info = data.get('data', {})
        countries_count = len(form_info.get('countries', []))
        job_titles_count = len(form_info.get('job_titles', []))
        contact_reasons_count = len(form_info.get('contact_reasons', []))
        
        print(f"Countries: {countries_count}")
        print(f"Job Titles: {job_titles_count}")
        print(f"Contact Reasons: {contact_reasons_count}")
        
        # Print required and optional fields
        print(f"Required Fields: {form_info.get('required_fields', [])}")
        print(f"Optional Fields: {form_info.get('optional_fields', [])}")
        
        # Print a few sample countries
        countries = form_info.get('countries', [])
        if countries:
            print("\nSample Countries:")
            for country in countries[:5]:
                print(f"  - {country.get('name_en')} ({country.get('code')})")
            print("  ...")
        
        return data
    else:
        print(f"Error: {response.text}")
        return None

if __name__ == "__main__":
    test_get_demo_form_info()
