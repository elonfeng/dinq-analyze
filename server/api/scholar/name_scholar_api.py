"""
Name Scholar API

This module provides an API endpoint for retrieving scholar information by name.
It uses the get_scholar_information method from account/name_scholar.py.
"""

import logging
from flask import Blueprint, request, jsonify, g
from account.name_scholar import get_scholar_information
from server.utils.auth import require_verified_user
from server.utils.logging_config import setup_logging
import re
# Create blueprint
name_scholar_bp = Blueprint('name_scholar', __name__)

# Configure logging
logger = logging.getLogger('server.api.scholar.name_scholar')

@name_scholar_bp.route('/api/scholar/by-name', methods=['GET', 'POST'])
@require_verified_user
def get_scholar_by_name():
    """
    Get scholar information by name.
    
    This endpoint accepts both GET and POST requests:
    - GET: query parameter 'name' contains the scholar name
    - POST: JSON body with 'name' field contains the scholar name
    
    Returns:
        JSON response with scholar information
    """
    try:
        # Get scholar name from request
        if request.method == 'GET':
            scholar_name = request.args.get('name', '')
        else:  # POST
            data = request.get_json()
            if not data or 'name' not in data:
                return jsonify({"error": "Missing name parameter"}), 400
            scholar_name = data['name']
        
        # Check if name parameter exists
        if not scholar_name:
            return jsonify({"error": "Missing name parameter"}), 400
        
        # Log the request with user information
        user_id = g.user_id if hasattr(g, 'user_id') else 'anonymous'
        logger.info(f"Scholar name lookup request from user {user_id}: {scholar_name}")
        
        # Get scholar information
        max_length = int(request.args.get('max_length', 2000))
        max_retries = int(request.args.get('max_retries', 3))
        
        scholar_info = get_scholar_information(
            scholar_name, 
            max_length=max_length,
            max_retries=max_retries
        )
        
        # Log the result
        if scholar_info and scholar_info.get('scholar_id'):
            logger.info(f"Found scholar ID for '{scholar_name}': {scholar_info.get('scholar_id')}")
        else:
            logger.warning(f"No scholar ID found for '{scholar_name}'")
            if 'error' in scholar_info:
                logger.error(f"Error getting scholar information: {scholar_info.get('error')}")
        
        # Return the result
        return jsonify(scholar_info)
        
    except Exception as e:
        logger.error(f"Error in get_scholar_by_name API: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
