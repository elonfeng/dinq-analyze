#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Talents API 的脚本

这个脚本提供了一个简单的方式来测试 Talents API 的功能。
"""

import os
import sys
import json
import argparse
import requests

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import the talents handler
from server.api.talents_handler import get_top_talents, process_institution_field

def test_process_institution_field():
    """
    Test the process_institution_field function.
    """
    print("Testing process_institution_field function...")
    
    # Test case 1: Institution with image URL
    talent1 = {
        "name": "Test Person",
        "institution": "Test University; https://example.com/image.png"
    }
    processed1 = process_institution_field(talent1)
    print("\nTest case 1:")
    print(f"Original: {talent1}")
    print(f"Processed: {processed1}")
    
    # Test case 2: Institution without image URL
    talent2 = {
        "name": "Test Person",
        "institution": "Test University"
    }
    processed2 = process_institution_field(talent2)
    print("\nTest case 2:")
    print(f"Original: {talent2}")
    print(f"Processed: {processed2}")
    
    # Test case 3: No institution field
    talent3 = {
        "name": "Test Person"
    }
    processed3 = process_institution_field(talent3)
    print("\nTest case 3:")
    print(f"Original: {talent3}")
    print(f"Processed: {processed3}")

def test_get_top_talents():
    """
    Test the get_top_talents function.
    """
    print("\nTesting get_top_talents function...")
    
    # Get top talents
    result = get_top_talents(3)
    
    # Print the result
    print(json.dumps(result, indent=2))
    
    # Check if institution and institution_image fields are correctly separated
    if result["success"] and result["talents"]:
        for i, talent in enumerate(result["talents"]):
            print(f"\nTalent {i+1}: {talent['name']}")
            print(f"Institution: {talent['institution']}")
            print(f"Institution Image: {talent['institution_image']}")

def test_talents_api(base_url):
    """
    Test the Talents API endpoint.
    
    Args:
        base_url: API base URL
    """
    print(f"\nTesting Talents API at {base_url}...")
    
    try:
        # Make API request
        response = requests.get(f"{base_url}/api/talents?count=3")
        response.raise_for_status()
        
        # Parse response
        result = response.json()
        
        # Print the result
        print(json.dumps(result, indent=2))
        
        # Check if institution and institution_image fields are correctly separated
        if result["success"] and result["talents"]:
            for i, talent in enumerate(result["talents"]):
                print(f"\nTalent {i+1}: {talent['name']}")
                print(f"Institution: {talent['institution']}")
                print(f"Institution Image: {talent.get('institution_image', 'Not available')}")
    
    except requests.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response content: {e.response.text}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Test Talents API')
    parser.add_argument('--api-test', action='store_true', help='Test the API endpoint')
    parser.add_argument('--base-url', default='http://localhost:5001', help='API base URL')
    
    args = parser.parse_args()
    
    # Test the process_institution_field function
    test_process_institution_field()
    
    # Test the get_top_talents function
    test_get_top_talents()
    
    # Test the API endpoint if requested
    if args.api_test:
        test_talents_api(args.base_url)

if __name__ == '__main__':
    main()
