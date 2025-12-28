"""
Process Countries

This script processes the country data from reports/contry.txt into a JSON file.
"""

import os
import json
import sys

# Add the project root to the Python path to enable absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def process_countries():
    """Process the country data from reports/contry.txt into a JSON file."""
    # Get the path to the country file
    country_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'reports', 'contry.txt'
    )
    
    # Get the path to the output JSON file
    output_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'countries.json'
    )
    
    # Create the data directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    
    # Read the country file
    with open(country_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Parse the header
    header = lines[0].strip().split('\t')
    
    # Parse the countries
    countries = []
    for line in lines[1:]:
        values = line.strip().split('\t')
        if len(values) >= 3:  # Ensure we have at least name and code
            country = {
                'name_zh': values[0],
                'name_en': values[1],
                'code': values[2],
                'continent': values[3] if len(values) > 3 else '',
                'region': values[4] if len(values) > 4 else '',
                'domain': values[5] if len(values) > 5 else '',
                'phone_code': values[6] if len(values) > 6 else ''
            }
            countries.append(country)
    
    # Sort countries by English name
    countries.sort(key=lambda x: x['name_en'])
    
    # Write the JSON file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(countries, f, ensure_ascii=False, indent=2)
    
    print(f"Processed {len(countries)} countries and saved to {output_file_path}")
    return countries

if __name__ == "__main__":
    process_countries()
