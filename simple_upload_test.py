#!/usr/bin/env python3
"""
Simple Image Upload Test

This script uploads a specified image file and tests the upload API.
"""

import requests
import json
import os
import sys
import argparse
from io import BytesIO
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:5001"
TEST_USER_ID = "NmlwRLtDyxZz1YjnJ5PvJdUWdPj2"

def read_file_from_path(file_path):
    """Read a file from the specified path."""
    try:
        with open(file_path, 'rb') as f:
            return BytesIO(f.read()), os.path.basename(file_path)
    except Exception as e:
        print(f"❌ Error reading file {file_path}: {e}")
        sys.exit(1)

def test_upload(file_path, bucket='demo', folder='test'):
    """Test the upload endpoint with a specified file."""
    print("Testing image upload API...")
    print(f"File to upload: {file_path}")
    
    # Read file from path
    file_content, file_name = read_file_from_path(file_path)
    
    # Determine content type based on file extension
    content_type = 'application/octet-stream'  # Default
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
        content_type = f"image/{Path(file_path).suffix[1:].lower()}"
        if Path(file_path).suffix[1:].lower() == 'jpg':
            content_type = 'image/jpeg'
    
    # Prepare the request
    files = {
        'file': (file_name, file_content, content_type)
    }
    
    data = {
        'bucket': bucket,
        'folder': folder
    }
    
    headers = {
        'Userid': TEST_USER_ID
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/upload-image",
            files=files,
            data=data,
            headers=headers,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the server is running on localhost:5001")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Upload a file to the server')
    parser.add_argument('file_path', default='/Users/aihe/Desktop/2025-05-21T06-56-55-280Z.png', help='Path to the file to upload')
    parser.add_argument('--bucket', default='demo', help='Bucket name (default: demo)')
    parser.add_argument('--folder', default='test', help='Folder name (default: test)')
    parser.add_argument('--api-url', default=API_BASE_URL, help=f'API base URL (default: {API_BASE_URL})')
    parser.add_argument('--user-id', default=TEST_USER_ID, help='User ID for authentication')
    
    return parser.parse_args()

def main():
    """Main test function."""
    args = parse_arguments()
    
    # Update global variables if provided in arguments
    global API_BASE_URL, TEST_USER_ID
    if args.api_url:
        API_BASE_URL = args.api_url
    if args.user_id:
        TEST_USER_ID = args.user_id
    
    print("Starting file upload test...")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print("-" * 50)
    
    # Verify file exists
    if not os.path.isfile(args.file_path):
        print(f"❌ Error: File not found at {args.file_path}")
        return False
    
    success = test_upload(args.file_path, args.bucket, args.folder)
    
    if success:
        print("✅ Upload test passed!")
    else:
        print("❌ Upload test failed!")

if __name__ == "__main__":
    main()
