# 根据如下信息, 基于Tavily找到学者的个人照片和官网.
# Fetching details for Scholar ID: QTgxKmkAAAAJ...
# Found author: Peng Zhang, Affiliation: Tongyi Lab, Alibaba Group, Email: Not available

# === Author Details Summary ===
# Full Name                      Affiliation                                        h-index  Citations

# ----------------------------------------------------------------------------------------------------
# Peng Zhang                     Tongyi Lab, Alibaba Group                          8        663   

import requests
import os
import time
from PIL import Image
import urllib.parse
import io
import json

# Define the default avatar URL
DEFAULT_AVATAR_URL = "https://static.vecteezy.com/system/resources/previews/005/544/718/original/profile-icon-design-free-vector.jpg"

def fetch_default_avatar():
    """Fetch the default avatar from the specified URL."""
    try:
        response = requests.get(DEFAULT_AVATAR_URL, timeout=10)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content))
        return img
    except Exception as e:
        print(f"Error fetching default avatar: {e}")
        # Create a blank image as fallback
        return Image.new('RGB', (150, 150), color="#CCCCCC")

def fetch_scholar_data_with_tavily(scholar_id, known_info, tavily_api_key):
    """
    Fetch scholar data using Tavily API.
    
    Args:
        scholar_id: Google Scholar ID
        known_info: Dictionary containing known information about the scholar
        tavily_api_key: Tavily API key
    """
    url = "https://api.tavily.com/search"
    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {tavily_api_key}"
    }
    
    # Construct a search query for the scholar including known information
    query = f"Google Scholar profile picture and details of author {known_info.get('name', '')} with ID {scholar_id}"
    
    if known_info.get('affiliation'):
        query += f", who works at {known_info.get('affiliation')}"
    
    payload = {
        "query": query,
        "search_depth": "advanced",
        "include_images": True,
        "include_answer": True,
        "max_results": 5
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error with Tavily API: {e}")
        return None

def extract_scholar_info(tavily_response, scholar_id, known_info):
    """Extract scholar information from Tavily API response."""
    # Start with the known information
    scholar_info = {
        'name': known_info.get('name', "Unknown"),
        'affiliation': known_info.get('affiliation', "Unknown"),
        'metrics': {'citations': known_info.get('citations', "N/A"), 'h_index': known_info.get('h_index', "N/A")},
        'image_url': None
    }
    
    if not tavily_response:
        return scholar_info
    
    # Check if there are any images returned
    if 'images' in tavily_response and tavily_response['images']:
        for image in tavily_response['images']:
            # Look for profile-like images
            if isinstance(image, dict):
                alt_text = image.get('alt_text', '').lower()
                if any(keyword in alt_text for keyword in ['profile', 'photo', 'portrait', 'headshot']):
                    scholar_info['image_url'] = image.get('url')
                    break
                
                # Look for images with the scholar's name in the alt text
                if scholar_info['name'].lower() in alt_text:
                    scholar_info['image_url'] = image.get('url')
                    break
            elif isinstance(image, str):
                # If image is a string (URL), just use it
                scholar_info['image_url'] = image
                break
        
        # If no profile image was found, just take the first image
        if scholar_info['image_url'] is None and tavily_response['images']:
            first_image = tavily_response['images'][0]
            if isinstance(first_image, dict):
                scholar_info['image_url'] = first_image.get('url')
            elif isinstance(first_image, str):
                scholar_info['image_url'] = first_image
    
    # Try to extract metrics from context if not already known
    if scholar_info['metrics']['citations'] == "N/A" or scholar_info['metrics']['h_index'] == "N/A":
        if 'context' in tavily_response:
            for context_item in tavily_response['context']:
                content = context_item.get('content', '').lower()
                
                # Look for citation metrics
                if 'citation' in content or 'h-index' in content:
                    lines = content.split('\n')
                    for line in lines:
                        if 'citation' in line and scholar_info['metrics']['citations'] == "N/A":
                            try:
                                citations = ''.join(filter(str.isdigit, line.split('citation')[1]))
                                if citations:
                                    scholar_info['metrics']['citations'] = citations
                            except:
                                pass
                        
                        if 'h-index' in line and scholar_info['metrics']['h_index'] == "N/A":
                            try:
                                h_index = ''.join(filter(str.isdigit, line.split('h-index')[1]))
                                if h_index:
                                    scholar_info['metrics']['h_index'] = h_index
                            except:
                                pass
    
    return scholar_info

def fetch_image(url):
    """Fetch an image from URL and return as PIL Image object."""
    try:
        if not url:
            return fetch_default_avatar(), False
            
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content))
        return img, True
    except Exception as e:
        print(f"Error fetching image from {url}: {e}")
        return fetch_default_avatar(), False

def main():
    # Get Tavily API key from environment variable or enter it here
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_api_key:
        tavily_api_key = input("Please enter your Tavily API key: ")
    
    # List of scholar IDs with known information
    scholars = [
        {
            "id": "QTgxKmkAAAAJ",
            "name": "Peng Zhang",
            "affiliation": "Tongyi Lab, Alibaba Group",
            "h_index": "8",
            "citations": "663"
        },
        # {
        #     "id": "Cvaq9KQAAAAJ",
        #     "name": "Jinwei Qi",
        #     "affiliation": "Alibaba DAMO Academy",
        #     "h_index": "",
        #     "citations": ""
        # }
    ]
    
    # Create output directory if it doesn't exist
    output_dir = "images/scholar_images"
    os.makedirs(output_dir, exist_ok=True)
    
    for scholar in scholars:
        scholar_id = scholar["id"]
        print(f"Fetching details for Scholar ID: {scholar_id}...")
        
        # Get scholar details using Tavily
        tavily_response = fetch_scholar_data_with_tavily(scholar_id, scholar, tavily_api_key)
        scholar_info = extract_scholar_info(tavily_response, scholar_id, scholar)
        
        # Fetch the image
        img, success = fetch_image(scholar_info['image_url'])
        
        # Save the image
        scholar_name = scholar_info['name'].replace(" ", "_")
        filename = f"{output_dir}/{scholar_id}_{scholar_name}.png"
        img.save(filename)
        
        # Print results
        print(f"Found author: {scholar_info['name']}, Affiliation: {scholar_info['affiliation']}")
        if success:
            print(f"✓ Image saved to {filename}")
        else:
            print(f"✗ No image found. Default avatar saved to {filename}")
        
        print("=== Author Details Summary ===")
        print(f"{'Full Name':<30} {'Affiliation':<50} {'h-index':<10} {'Citations':<10}")
        print("-" * 100)
        print(f"{scholar_info['name']:<30} {scholar_info['affiliation']:<50} {scholar_info['metrics']['h_index']:<10} {scholar_info['metrics']['citations']:<10}")
        
        # Save the full scholar info to a JSON file
        with open(f"{output_dir}/{scholar_id}_info.json", 'w') as f:
            json.dump(scholar_info, f, indent=2)
        
        print(f"Scholar info saved to {output_dir}/{scholar_id}_info.json")
        print()
        
        # Add a delay to avoid rate limiting
        time.sleep(2)

if __name__ == "__main__":
    main()
