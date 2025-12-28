#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Name Scholar API

This script tests the Name Scholar API endpoint.
"""

import os
import sys
import json
import requests

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Base URL for API requests
BASE_URL = "http://localhost:5001"

# Test user ID for authentication
TEST_USER_ID = "LtXQ0x62DpOB88r1x3TL329FbHk1"

def test_get_scholar_by_name():
    """Test the GET /api/scholar/by-name endpoint."""
    print("\n=== Testing GET /api/scholar/by-name ===")
    
    # Test cases
    test_cases = [
        "qiang wang, apple ai",
        "Timo Aila",
        "John Smith, MIT"
    ]
    
    for name in test_cases:
        print(f"\nTesting with name: {name}")
        
        # Make the request
        url = f"{BASE_URL}/api/scholar/by-name?name={requests.utils.quote(name)}"
        headers = {"userid": TEST_USER_ID}  # Add authentication header
        
        try:
            response = requests.get(url, headers=headers)
            
            # Check response status
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("Response data:")
                print(json.dumps(data, indent=2))
                
                # Check if scholar_id is present
                if data.get('scholar_id'):
                    print(f"✅ Found scholar ID: {data.get('scholar_id')}")
                else:
                    print("❌ No scholar ID found")
                    if 'error' in data:
                        print(f"Error: {data.get('error')}")
            else:
                print(f"❌ Request failed: {response.text}")
        
        except Exception as e:
            print(f"❌ Exception: {str(e)}")

def test_post_scholar_by_name():
    """Test the POST /api/scholar/by-name endpoint."""
    print("\n=== Testing POST /api/scholar/by-name ===")
    
    # Test cases
    test_cases = [
        "qiang wang, apple ai",
        "Timo Aila",
        "John Smith, MIT"
    ]
    
    for name in test_cases:
        print(f"\nTesting with name: {name}")
        
        # Make the request
        url = f"{BASE_URL}/api/scholar/by-name"
        headers = {
            "userid": TEST_USER_ID,  # Add authentication header
            "Content-Type": "application/json"
        }
        data = {"name": name}
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            # Check response status
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("Response data:")
                print(json.dumps(data, indent=2))
                
                # Check if scholar_id is present
                if data.get('scholar_id'):
                    print(f"✅ Found scholar ID: {data.get('scholar_id')}")
                else:
                    print("❌ No scholar ID found")
                    if 'error' in data:
                        print(f"Error: {data.get('error')}")
            else:
                print(f"❌ Request failed: {response.text}")
        
        except Exception as e:
            print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    # Run the tests
    test_get_scholar_by_name()
    test_post_scholar_by_name()
