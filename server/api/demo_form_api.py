"""
Demo Form API

This module provides API endpoints for the demo request form.
It returns form information including country list.
"""

import os
import json
import logging
from flask import Blueprint, jsonify

# Create blueprint
demo_form_bp = Blueprint('demo_form', __name__)

# Configure logging
logger = logging.getLogger(__name__)

@demo_form_bp.route('/api/demo-form/info', methods=['GET'])
def get_demo_form_info():
    """
    Get information for the demo request form.
    
    Returns:
        JSON response with form information including country list
    """
    try:
        # Get the path to the countries JSON file
        countries_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data', 'countries.json'
        )
        
        # Read the countries JSON file
        with open(countries_file_path, 'r', encoding='utf-8') as f:
            countries = json.load(f)
        
        # Define job title options
        job_titles = [
            "Professor",
            "Associate Professor",
            "Assistant Professor",
            "Researcher",
            "Research Scientist",
            "Data Scientist",
            "Software Engineer",
            "Product Manager",
            "Student",
            "Other"
        ]
        
        # Define contact reason options
        contact_reasons = [
            "Academic research",
            "Commercial use",
            "Educational purposes",
            "Partnership opportunity",
            "General inquiry",
            "Other"
        ]
        
        # Create form information
        form_info = {
            "countries": countries,
            "job_titles": job_titles,
            "contact_reasons": contact_reasons,
            "required_fields": [
                "email",
                "affiliation",
                "country",
                "job_title",
                "contact_reason"
            ],
            "optional_fields": [
                "additional_details",
                "marketing_consent"
            ]
        }
        
        return jsonify({
            "success": True,
            "data": form_info
        })
    except Exception as e:
        logger.error(f"Error getting demo form information: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"An error occurred: {str(e)}"
        }), 500
