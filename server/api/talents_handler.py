"""
Top AI Talents Handler

This module provides functions for retrieving top AI talents from the CSV file.
"""

import os
import csv
import random
from typing import List, Dict, Any

def get_csv_path() -> str:
    """
    Get the path to the top_ai_talents.csv file.

    Returns:
        str: Absolute path to the CSV file
    """
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Path to the CSV file
    csv_path = os.path.join(project_root, 'top_ai_talents.csv')

    return csv_path

def read_talents_from_csv() -> List[Dict[str, str]]:
    """
    Read all talents from the CSV file.

    Returns:
        List[Dict[str, str]]: List of talents as dictionaries
    """
    csv_path = get_csv_path()

    # Check if the file exists
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at {csv_path}")

    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'gbk', 'gb2312', 'gb18030', 'big5']

    for encoding in encodings:
        try:
            # Read the CSV file
            talents = []
            with open(csv_path, 'r', encoding=encoding) as file:
                reader = csv.DictReader(file)
                for row in reader:
                    talents.append(row)

            print(f"Successfully read CSV with encoding: {encoding}")
            return talents
        except UnicodeDecodeError:
            print(f"Failed to read CSV with encoding: {encoding}")
            continue

    # If all encodings fail, raise an exception
    raise UnicodeDecodeError("csv", b"", 0, 1, "Failed to decode CSV file with any encoding")

def process_institution_field(talent: Dict[str, str]) -> Dict[str, str]:
    """
    Process the institution field to separate institution name and image URL.

    Args:
        talent (Dict[str, str]): Talent dictionary

    Returns:
        Dict[str, str]: Updated talent dictionary with separated institution fields
    """
    # Make a copy of the talent dictionary to avoid modifying the original
    processed_talent = talent.copy()

    # Check if institution field exists and contains a semicolon
    if 'institution' in processed_talent and ';' in processed_talent['institution']:
        # Split the institution field by semicolon
        parts = processed_talent['institution'].split(';', 1)

        # Set the institution field to just the name (trimmed)
        processed_talent['institution'] = parts[0].strip()

        # If there's an image URL part, add it as a new field
        if len(parts) > 1 and parts[1].strip():
            processed_talent['institution_image'] = parts[1].strip()
        else:
            processed_talent['institution_image'] = ""
    else:
        # If there's no semicolon, just add an empty institution_image field
        processed_talent['institution_image'] = ""

    return processed_talent

def get_random_talents(count: int = 5) -> List[Dict[str, str]]:
    """
    Get a random selection of talents from the CSV file.

    Args:
        count (int): Number of talents to return (default: 5)

    Returns:
        List[Dict[str, str]]: List of randomly selected talents with processed fields
    """
    # Read all talents from the CSV file
    all_talents = read_talents_from_csv()

    # If there are fewer talents than requested, return all of them
    if len(all_talents) <= count:
        selected_talents = all_talents
    else:
        # Randomly select the requested number of talents
        selected_talents = random.sample(all_talents, count)

    # Process each talent to separate institution and institution_image
    processed_talents = [process_institution_field(talent) for talent in selected_talents]

    return processed_talents

def get_top_talents(count: int = 5) -> Dict[str, Any]:
    """
    Get top AI talents for the API response.

    Args:
        count (int): Number of talents to return (default: 5)

    Returns:
        Dict[str, Any]: API response with talents data
    """
    try:
        # Get random talents
        talents = get_random_talents(count)

        # Prepare the response
        response = {
            "success": True,
            "count": len(talents),
            "talents": talents
        }

        return response
    except Exception as e:
        # Return error response
        return {
            "success": False,
            "error": str(e)
        }
