"""
LinkedIn Talents Handler

This module provides functions for retrieving top LinkedIn talents from the CSV file.
"""

import os
import csv
import random
import re
from typing import List, Dict, Any

def get_csv_path() -> str:
    """
    Get the path to the linkedin.csv file.

    Returns:
        str: Absolute path to the CSV file
    """
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Path to the CSV file
    csv_path = os.path.join(project_root, 'server', 'linkedin_analyzer', 'linkedin.csv')

    return csv_path

def read_talents_from_csv() -> List[Dict[str, str]]:
    """
    Read all LinkedIn talents from the CSV file.

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
                    # Skip empty rows
                    if not any(row.values()):
                        continue
                    talents.append(row)

            print(f"Successfully read LinkedIn CSV with encoding: {encoding}")
            return talents
        except UnicodeDecodeError:
            print(f"Failed to read LinkedIn CSV with encoding: {encoding}")
            continue

    # If all encodings fail, raise an exception
    raise UnicodeDecodeError("csv", b"", 0, 1, "Failed to decode LinkedIn CSV file with any encoding")

def process_talent_data(talent: Dict[str, str]) -> Dict[str, str]:
    """
    Process talent data to clean and standardize fields.

    Args:
        talent (Dict[str, str]): Raw talent dictionary

    Returns:
        Dict[str, str]: Processed talent dictionary
    """
    # Remove empty keys first
    processed_talent = {k: v for k, v in talent.items() if k.strip()}

    # Clean and standardize field names
    field_mapping = {
        'Name': 'name',
        'linkedin': 'linkedin_url',
        'Image': 'photo_url',
        'Company Logo': 'company_logo',
        'Company': 'company',
        'Title': 'title',
        'salary': 'salary',
        'remark': 'remark'
    }

    # Apply field mapping
    for old_key, new_key in field_mapping.items():
        if old_key in processed_talent:
            processed_talent[new_key] = processed_talent.pop(old_key)

    # Clean salary field - extract numeric range
    salary = processed_talent.get('salary', '')
    if salary:
        processed_talent['salary_display'] = salary
        # Try to extract numeric value for sorting
        try:
            # Extract first number from salary string (re imported at top)
            numbers = re.findall(r'\d+', salary.replace(',', ''))
            if numbers:
                processed_talent['salary_numeric'] = int(numbers[0])
            else:
                processed_talent['salary_numeric'] = 0
        except:
            processed_talent['salary_numeric'] = 0
    else:
        processed_talent['salary_display'] = 'Not disclosed'
        processed_talent['salary_numeric'] = 0

    # Clean URLs
    for url_field in ['linkedin_url', 'photo_url', 'company_logo']:
        if url_field in processed_talent and processed_talent[url_field]:
            url = processed_talent[url_field].strip()
            if url and not url.startswith('http'):
                if url_field == 'linkedin_url':
                    processed_talent[url_field] = f"https://{url}"
                else:
                    processed_talent[url_field] = url
        else:
            processed_talent[url_field] = ""

    # Ensure required fields exist
    required_fields = ['name', 'company', 'title', 'linkedin_url', 'photo_url']
    for field in required_fields:
        if field not in processed_talent:
            processed_talent[field] = ""

    return processed_talent

def filter_talents(talents: List[Dict[str, str]], company_filter: str = None,
                  title_filter: str = None, min_salary: int = None) -> List[Dict[str, str]]:
    """
    Filter talents based on criteria.

    Args:
        talents: List of talent dictionaries
        company_filter: Filter by company name (partial match)
        title_filter: Filter by title (partial match)
        min_salary: Minimum salary in millions

    Returns:
        Filtered list of talents
    """
    filtered = talents

    if company_filter:
        filtered = [t for t in filtered if company_filter.lower() in t.get('company', '').lower()]

    if title_filter:
        filtered = [t for t in filtered if title_filter.lower() in t.get('title', '').lower()]

    if min_salary is not None:
        filtered = [t for t in filtered if t.get('salary_numeric', 0) >= min_salary]

    return filtered

def get_random_talents(count: int = 5) -> List[Dict[str, str]]:
    """
    Get a random selection of LinkedIn talents from the CSV file.

    Args:
        count (int): Number of talents to return (default: 5)

    Returns:
        List[Dict[str, str]]: List of randomly selected talents with processed fields
    """
    # Read all talents from the CSV file
    all_talents = read_talents_from_csv()

    # Process each talent
    processed_talents = [process_talent_data(talent) for talent in all_talents]

    # If there are fewer talents than requested, return all of them
    if len(processed_talents) <= count:
        selected_talents = processed_talents
    else:
        # Randomly select the requested number of talents
        selected_talents = random.sample(processed_talents, count)

    return selected_talents

def get_top_linkedin_talents(count: int = 3, company_filter: str = None,
                           title_filter: str = None, min_salary: int = None) -> Dict[str, Any]:
    """
    Get top LinkedIn talents for the API response.

    Args:
        count (int): Number of talents to return (default: 5)
        company_filter (str): Filter by company name
        title_filter (str): Filter by title
        min_salary (int): Minimum salary filter

    Returns:
        Dict[str, Any]: API response with talents data
    """
    try:
        # Read and process all talents
        all_talents = read_talents_from_csv()
        processed_talents = [process_talent_data(talent) for talent in all_talents]

        # Apply filters
        filtered_talents = filter_talents(processed_talents, company_filter, title_filter, min_salary)

        # Select talents with better diversity
        if len(filtered_talents) <= count:
            selected_talents = filtered_talents
        else:
            # Provide more diverse selection instead of always focusing on highest salaries
            # Mix of high-salary and diverse talents
            sorted_talents = sorted(filtered_talents, key=lambda x: x.get('salary_numeric', 0), reverse=True)

            # Take top 50% for high-salary pool and bottom 50% for diversity pool
            mid_point = len(sorted_talents) // 2
            high_salary_pool = sorted_talents[:mid_point]
            diverse_pool = sorted_talents[mid_point:]

            # Select mix: 60% from high-salary pool, 40% from diverse pool
            high_salary_count = max(1, int(count * 0.6))
            diverse_count = count - high_salary_count

            selected_talents = []

            # Select from high-salary pool
            if len(high_salary_pool) >= high_salary_count:
                selected_talents.extend(random.sample(high_salary_pool, high_salary_count))
            else:
                selected_talents.extend(high_salary_pool)

            # Select from diverse pool to fill remaining slots
            remaining_slots = count - len(selected_talents)
            if remaining_slots > 0 and diverse_pool:
                if len(diverse_pool) >= remaining_slots:
                    selected_talents.extend(random.sample(diverse_pool, remaining_slots))
                else:
                    selected_talents.extend(diverse_pool)

            # If still not enough, fill from all available
            if len(selected_talents) < count:
                remaining_talents = [t for t in filtered_talents if t not in selected_talents]
                remaining_needed = count - len(selected_talents)
                if remaining_talents and remaining_needed > 0:
                    additional = random.sample(remaining_talents, min(remaining_needed, len(remaining_talents)))
                    selected_talents.extend(additional)

        # Prepare the response
        response = {
            "success": True,
            "count": len(selected_talents),
            "talents": selected_talents,
            "total_available": len(filtered_talents)
        }

        return response
    except Exception as e:
        # Return error response
        return {
            "success": False,
            "error": str(e)
        }
