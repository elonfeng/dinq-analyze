#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试机构字段拆分功能
"""

import json

def process_institution_field(talent):
    """
    Process the institution field to separate institution name and image URL.
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

def main():
    # Test data from the example
    test_data = {
        "count": 5,
        "success": True,
        "talents": [
            {
                "citation": "190587",
                "famous_work": "Attention is all you need 2017",
                "google_scholar": "q2YXPSgAAAAJ",
                "honor": "",
                "image": "https://miro.medium.com/v2/resize:fit:1400/0*iH1nF6xxkDvFWRmt",
                "institution": "Essential AI; https://montgomerysummit.com/wp-content/uploads/Essential-AI-TileUnofficial.png",
                "linkedin": "https://www.linkedin.com/in/nikiparmar",
                "name": "Niki Parmar",
                "personal_page": "",
                "position": "Co-Founder",
                "twitter": "nikiparmar09"
            },
            {
                "citation": "316217",
                "famous_work": "Seq2Seq 2014",
                "google_scholar": "vfT6-XIAAAAJ",
                "honor": "",
                "image": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQHQM0-a6JR72guroGOsZN6Tp8JdE6WQ5x_bryB5H0W44M0uHYGKwam5WfvgQjxzCoIbGc&usqp=CAU",
                "institution": "Google; https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/Google_2015_logo.svg/1200px-Google_2015_logo.svg.png",
                "linkedin": "https://www.linkedin.com/in/quoc-v-le-319b5a8",
                "name": "Quoc V. Le",
                "personal_page": "https://cs.stanford.edu/~quocle/",
                "position": "Research Scientist",
                "twitter": "quocleix"
            }
        ]
    }
    
    # Process each talent
    processed_talents = []
    for talent in test_data["talents"]:
        processed_talent = process_institution_field(talent)
        processed_talents.append(processed_talent)
    
    # Update the test data
    test_data["talents"] = processed_talents
    
    # Print the processed data
    print(json.dumps(test_data, indent=4))

if __name__ == "__main__":
    main()
