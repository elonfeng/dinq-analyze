"""
Test script for the demo request API.

This script tests the demo request API endpoints.
"""

import sys
import os
import json
import requests

# Add the project root to the Python path to enable absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Base URL for API requests
BASE_URL = "http://localhost:5002"

# Test user ID for authentication
TEST_USER_ID = "gAckWxWYazcI5k95n627hRBHB712"

def test_submit_demo_request():
    """Test submitting a demo request."""
    print("\n=== Testing Demo Request Submission ===")

    # Prepare request data
    url = f"{BASE_URL}/api/demo-request"
    headers = {
        "Content-Type": "application/json",
        "userid": TEST_USER_ID
    }

    # Test data
    data = {
        "email": "test@example.com",
        "affiliation": "Test University",
        "country": "United States",
        "job_title": "Researcher",
        "contact_reason": "Interested in using the product for research",
        "additional_details": "Would like to know more about pricing and features",
        "marketing_consent": True
    }

    # Send request
    print(f"Sending POST request to {url}")
    response = requests.post(url, headers=headers, json=data)

    # Print response
    print(f"Status code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    # Verify response
    if response.status_code == 200 and response.json().get('success'):
        print("✅ Demo request submitted successfully")
    else:
        print("❌ Failed to submit demo request")

    return response.json() if response.status_code == 200 else None

def test_get_my_demo_requests():
    """Test retrieving user's demo requests."""
    print("\n=== Testing Get My Demo Requests ===")

    # Prepare request
    url = f"{BASE_URL}/api/demo-request/my-requests"
    headers = {
        "Content-Type": "application/json",
        "userid": TEST_USER_ID
    }

    # Send request
    print(f"Sending GET request to {url}")
    response = requests.get(url, headers=headers)

    # Print response
    print(f"Status code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    # Verify response
    if response.status_code == 200 and response.json().get('success'):
        requests_count = len(response.json().get('data', {}).get('requests', []))
        print(f"✅ Retrieved {requests_count} demo requests")
    else:
        print("❌ Failed to retrieve demo requests")

def run_tests():
    """Run all tests."""
    # Submit a demo request
    test_submit_demo_request()

    # Get user's demo requests
    test_get_my_demo_requests()

if __name__ == "__main__":
    run_tests()
