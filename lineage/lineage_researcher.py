# coding: UTF-8 
"""
    @date: 20250430
    @author: Sam
    @func: Academic Lineage from OpenReview.
"""
import re
import os
import time
import json
import copy
import requests
from bs4 import BeautifulSoup
from crawlbase import CrawlingAPI
from typing import List, Dict, Any, Optional, Union, Tuple


def openreview_id_to_google_scholar_id(openreview_id: str) -> str:
    """
    Convert an OpenReview ID to a Google Scholar ID.
    """
    # Clean up the OpenReview ID by removing any duplicate 'profile?id=' patterns
    if 'profile?id=' in openreview_id:
        # Extract just the ID part after the last 'profile?id='
        openreview_id = openreview_id.split('profile?id=')[-1]
    
    # Ensure the ID starts with '~' if it doesn't already
    if not openreview_id.startswith('~'):
        openreview_id = f"~{openreview_id}"

    url = f"https://openreview.net/profile?id={openreview_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract Google Scholar ID
        scholar_id = None
        scholar_links = soup.find_all('a', href=lambda x: x and 'scholar.google' in x.lower())
        for link in scholar_links:
            href = link['href']
            match = re.search(r'user=([^&"\s]+)', href)
            if match:
                scholar_id = match.group(1)
                break
        return scholar_id
    except requests.exceptions.RequestException as e:
        print(f"Error fetching OpenReview profile: {e}")
        return None

def parse_lineage_content(content_string: str) -> list:
    """
    Parses the string content containing a JSON array of academic lineage.

    Args:
        content_string: The string containing the JSON data, potentially with surrounding text.

    Returns:
        A list of dictionaries representing the academic lineage, or an empty list if parsing fails.
    """
    try:
        # Use regex to find the JSON part within the string
        json_match = re.search(r'\[[\s\S]*?\]', content_string)
        if json_match:
            json_str = json_match.group(0)
            lineage_data = json.loads(json_str)
            return lineage_data
        else:
            print("No JSON array found in the content string.")
            return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        print(f"Problematic string: {content_string}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []


def agent_response(researcher_info: str, openrouter_key: str) -> List[Dict[str, Any]]:
    """Get detailed information about a researcher including photo and background."""
    try:
        from server.llm.gateway import openrouter_chat

        content = openrouter_chat(
            task="lineage.researcher",
            model="google/gemini-2.0-flash-001:online",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Given the following scholar's OpenReview profile information, extract their academic lineage: "
                        "first-order (direct coauthors or advisors) best AI researchers they have ever collaborated with. "
                        "For each, provide the reason for selection and relevant details. "
                        "You MUST only use names and information explicitly present in the input. Do not invent, infer, or guess any names or relationships. "
                        "Return at least 3 people but not more than 5. "
                        f"Input information: {researcher_info}\n"
                        "Return ONLY a strict JSON array, each item with the following fields: "
                        "name (string), reason (string), position_or_work (string), openreview_id (string). "
                        "No extra text, no markdown, just valid JSON."
                    ),
                }
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        content = str(content) if content else ""

        try:
            lineage_data = parse_lineage_content(content)
            return lineage_data
        except Exception as e:
            print(f"Error parsing LLM output: {e}")
            print(f"Problematic content: {content}")
            return []

    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def dict_to_plain_text(data: Dict) -> str:
    """Convert a dictionary to plain text description.
    
    Args:
        data: Dictionary containing profile information
        
    Returns:
        A plain text string describing the content
    """
    text_parts = []
    
    # Add name
    if "name" in data:
        text_parts.append(f"Scholar name: {data['name']}")
    
    # Add career history
    if "career_history" in data:
        text_parts.append("\nCareer History:")
        for position in data["career_history"]:
            text_parts.append(f"- {position['position']} at {position['institution']} during {position['timeframe']}")
    
    # Add relations
    if "relations" in data:
        text_parts.append("\nAcademic Relations:")
        for relation in data["relations"]:
            text_parts.append(f"- {relation['relation_type']}: {relation['name']} ({relation['timeframe']})")
    
    # Add coauthors
    if "coauthors" in data:
        text_parts.append("\nCo-authors:")
        text_parts.append(", ".join(data["coauthors"]))
    
    return "\n".join(text_parts)

def get_lineage(profile_json: str, openrouter_key: str, level: int = 1):
    """
    Get the academic lineage of a given profile.
    """
    with open(profile_json, 'r', encoding='utf-8') as f:
        profile_data = json.load(f)

    # profile_data.pop("expertise")
    # profile_data.pop("current_institution")
    
    output = agent_response(profile_data, openrouter_key)

    return output

def get_scholar_info(scholar_id: str, crawlbase_token: str) -> Dict[str, Any]:
    """
    Get scholar's profile image URL and total citations from Google Scholar.
    
    Args:
        scholar_id: Google Scholar ID
        crawlbase_token: Crawlbase API token for making requests
        
    Returns:
        Dictionary containing profile_image_url and total_citations
    """
    if not scholar_id:
        return {"profile_image_url": None, "total_citations": None}
        
    api = CrawlingAPI({'token': crawlbase_token})
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    
    try:
        response = api.get(url)
        if response['status_code'] != 200:
            print(f"Error fetching scholar profile: {response['status_code']}")
            return {"profile_image_url": None, "total_citations": None}
            
        html_content = response['body']
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Get profile image URL
        img_tag = soup.find('img', {'id': 'gsc_prf_pup-img'})
        profile_image_url = img_tag['src'] if img_tag else None
        
        # Get total citations
        citation_stats = soup.find('td', {'class': 'gsc_rsb_std'})
        total_citations = int(citation_stats.text) if citation_stats else None
        
        return {
            "profile_image_url": profile_image_url,
            "total_citations": total_citations
        }
        
    except Exception as e:
        print(f"Error getting scholar info: {e}")
        return {"profile_image_url": None, "total_citations": None}

if __name__ == "__main__":
    openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY") or ""
    crawlbase_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
    profile_json = "daiheng_gao_openreview_profile.json"
    output = get_lineage(profile_json, openrouter_key)

    final_output = copy.deepcopy(output)
    for idx, item in enumerate(output):
        if item['openreview_id'] is not None and item['openreview_id'] != "~N/A":
            scholar_id = openreview_id_to_google_scholar_id(item['openreview_id'])
            final_output[idx]['google_scholar_id'] = scholar_id
            if scholar_id:
                scholar_info = get_scholar_info(scholar_id, crawlbase_token)
                final_output[idx].update(scholar_info)
        else:
            final_output[idx]['google_scholar_id'] = None
            final_output[idx]['profile_image_url'] = None
            final_output[idx]['total_citations'] = None

    for item in final_output:
        print(item)
