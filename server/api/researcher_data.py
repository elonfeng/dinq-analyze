"""
Researcher Data API

This module handles researcher data API requests and responses.
"""

import os
import sys
import json
from typing import Dict, Any, Optional


def get_researcher_data() -> Dict[str, Any]:
    """
    Get researcher data from the JSON file.
    
    Returns:
        Dictionary containing researcher data
    
    Raises:
        FileNotFoundError: If the researcher data file is not found
        json.JSONDecodeError: If the researcher data file contains invalid JSON
    """
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Path to the researcher analysis JSON file
    json_file_path = os.path.join(project_root, 'researcher_analysis.json')
    
    # Check if the file exists
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"Researcher data file not found at {json_file_path}")
    
    # Read and parse the JSON file
    with open(json_file_path, 'r') as file:
        researcher_data = json.load(file)
    
    return researcher_data
