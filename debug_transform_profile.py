#!/usr/bin/env python3
"""
Debug script for transform_profile.py

This script helps debug the transform_profile.py module by providing a test case
with sample data containing level_info with evaluation_bars.
"""

import os
import sys
import json
import logging

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import logging configuration
from server.utils.logging_config import setup_logging

# Configure logging
logger = setup_logging()
logger = logging.getLogger(__name__)

# Import the transform_data function
from server.transform_profile import transform_data

def main():
    """Main function to test transform_profile.py"""
    # Sample data with level_info containing evaluation_bars
    sample_data = {
        "researcher": {
            "name": "Quoc V. Le",
            "abbreviated_name": "Q. Le",
            "affiliation": "Google Research",
            "email": "qvl@google.com",
            "research_fields": ["Machine Learning", "Deep Learning", "Neural Networks"],
            "total_citations": 100000,
            "h_index": 80
        },
        "publication_stats": {
            "total_papers": 150,
            "first_author_papers": 10,
            "last_author_papers": 30,
            "top_tier_papers": 50
        },
        "level_info": {
            "earnings": "1200000",
            "level_cn": "P9",
            "level_us": "L7",
            "justification": "Quoc V. Le is a highly impactful researcher with a significant number of citations and a high H-index, indicating substantial influence in AI and machine learning.",
            "evaluation_bars": {
                "depth_vs_breadth": {
                    "score": 8,
                    "explanation": "Quoc V. Le demonstrates depth with multiple papers in machine learning and AI, particularly in neural networks, as evidenced by his highly cited 'Sequence to sequence learning' paper."
                },
                "individual_vs_team": {
                    "score": 9,
                    "explanation": "With only 1.6% of his papers as first-author and frequent collaborations, notably with Barret Zoph, Quoc V. Le is highly team-oriented."
                },
                "theory_vs_practice": {
                    "score": 6,
                    "explanation": "His research includes both theoretical advancements, such as neural network models, and practical applications, as seen in his patents and real-world implementations."
                }
            },
            "years_of_experience": {
                "years": 15,
                "start_year": 2008,
                "calculation_basis": "The first publication listed is from 2008, and considering the current year as 2023, this results in 15 years of experience."
            }
        }
    }

    # Transform the data
    logger.info("Transforming sample data...")
    transformed_data = transform_data(sample_data)
    
    # Print the researcher character section
    character_data = transformed_data["researcherProfile"]["dataBlocks"]["researcherCharacter"]
    logger.info(f"Transformed researcher character data:")
    logger.info(f"Depth vs Breadth: {character_data['depthVsBreadth']}")
    logger.info(f"Theory vs Practice: {character_data['theoryVsPractice']}")
    logger.info(f"Solo vs Teamwork: {character_data['soloVsTeamwork']}")
    logger.info(f"Justification: {character_data['justification']}")
    
    # Save the transformed data to a file for inspection
    output_file = os.path.join(project_root, "debug_output.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(transformed_data, f, indent=2)
    
    logger.info(f"Transformed data saved to {output_file}")

if __name__ == "__main__":
    main()
