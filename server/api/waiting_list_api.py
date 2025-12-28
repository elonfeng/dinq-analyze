"""
Waiting List API

This module provides API endpoints for managing waiting list entries.
"""

import logging
from flask import Blueprint, request, jsonify, g

from server.utils.auth import require_auth, require_verified_user
from server.utils.user_utils import get_current_user_id
from src.utils.waiting_list_repository import waiting_list_repo

# Create blueprint
waiting_list_bp = Blueprint('waiting_list', __name__)

# Configure logging
logger = logging.getLogger('server.api.waiting_list')

@waiting_list_bp.route('/api/waiting-list/join', methods=['POST'])
@require_auth
def join_waiting_list():
    """
    Add the current user to the waiting list.
    
    Request body:
        email: User's email address (required)
        name: User's full name (required)
        organization: User's organization or company (optional)
        job_title: User's job title (optional)
        reason: Reason for joining the waiting list (optional)
        [additional fields]: Any additional fields will be stored in the metadata
        
    Returns:
        JSON response with the result of the operation
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User not authenticated"
            }), 401
            
        # Get request data
        data = request.get_json() or {}
        
        # Validate required fields
        email = data.get('email')
        name = data.get('name')
        
        if not email:
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400
            
        if not name:
            return jsonify({
                "success": False,
                "error": "Name is required"
            }), 400
            
        # Add to waiting list
        result = waiting_list_repo.add_to_waiting_list(user_id, email, name, data)
        
        # Check if operation was successful
        if not result.get('success'):
            return jsonify(result), 400
            
        # Return the result
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error joining waiting list: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@waiting_list_bp.route('/api/waiting-list/status', methods=['GET'])
@require_auth
def get_waiting_list_status():
    """
    Get the current user's waiting list status.
    
    Returns:
        JSON response with the user's waiting list entry
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User not authenticated"
            }), 401
            
        # Get waiting list entry
        result = waiting_list_repo.get_waiting_list_entry(user_id)
        
        # Return the result (even if entry not found)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting waiting list status: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@waiting_list_bp.route('/api/waiting-list/entries', methods=['GET'])
@require_verified_user
def get_waiting_list_entries():
    """
    Get waiting list entries with optional filtering.
    
    Query parameters:
        status: Filter by status (pending, approved, rejected)
        limit: Maximum number of entries to return (default: 100)
        offset: Offset for pagination (default: 0)
        
    Returns:
        JSON response with a list of waiting list entries
    """
    try:
        # Extract query parameters
        status = request.args.get('status')
        
        # Parse pagination parameters
        try:
            limit = min(100, max(1, int(request.args.get('limit', 100))))
        except ValueError:
            limit = 100
            
        try:
            offset = max(0, int(request.args.get('offset', 0)))
        except ValueError:
            offset = 0
            
        # Get waiting list entries
        result = waiting_list_repo.get_waiting_list(status, limit, offset)
        
        # Check if operation was successful
        if not result.get('success'):
            return jsonify(result), 400
            
        # Return the result
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting waiting list entries: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@waiting_list_bp.route('/api/waiting-list/update-status', methods=['POST'])
@require_verified_user
def update_waiting_list_status():
    """
    Update the status of a waiting list entry.
    
    Request body:
        user_id: The user ID of the entry to update (required)
        status: The new status (pending, approved, rejected) (required)
        
    Returns:
        JSON response with the result of the operation
    """
    try:
        # Get current user ID (for approved_by)
        admin_user_id = get_current_user_id()
        
        # Get request data
        data = request.get_json() or {}
        
        # Validate required fields
        user_id = data.get('user_id')
        status = data.get('status')
        
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User ID is required"
            }), 400
            
        if not status:
            return jsonify({
                "success": False,
                "error": "Status is required"
            }), 400
            
        # Update status
        result = waiting_list_repo.update_entry_status(user_id, status, admin_user_id if status == 'approved' else None)
        
        # Check if operation was successful
        if not result.get('success'):
            return jsonify(result), 400
            
        # Return the result
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error updating waiting list status: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@waiting_list_bp.route('/api/waiting-list/admin/entries', methods=['GET'])
def get_waiting_list_entries_admin():
    """
    Get waiting list entries with optional filtering (admin version).
    
    Query parameters:
        status: Filter by status (pending, approved, rejected)
        limit: Maximum number of entries to return (default: 100)
        offset: Offset for pagination (default: 0)
        
    Returns:
        JSON response with a list of waiting list entries
    """
    try:
        # Extract query parameters
        status = request.args.get('status')
        
        # Parse pagination parameters
        try:
            limit = min(100, max(1, int(request.args.get('limit', 100))))
        except ValueError:
            limit = 100
            
        try:
            offset = max(0, int(request.args.get('offset', 0)))
        except ValueError:
            offset = 0
            
        # Get waiting list entries
        result = waiting_list_repo.get_waiting_list(status, limit, offset)
        
        # Check if operation was successful
        if not result.get('success'):
            return jsonify(result), 400
            
        # Return the result
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting waiting list entries: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@waiting_list_bp.route('/api/waiting-list/admin/update-status', methods=['POST'])
def update_waiting_list_status_admin():
    """
    Update the status of a waiting list entry (admin version).
    
    Request body:
        user_id: The user ID of the entry to update (required)
        status: The new status (pending, approved, rejected) (required)
        
    Returns:
        JSON response with the result of the operation
    """
    try:
        # Get current user ID (for approved_by)
        admin_user_id = get_current_user_id()
        
        # Get request data
        data = request.get_json() or {}
        
        # Validate required fields
        user_id = data.get('user_id')
        status = data.get('status')
        
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User ID is required"
            }), 400
            
        if not status:
            return jsonify({
                "success": False,
                "error": "Status is required"
            }), 400
            
        # Update status
        result = waiting_list_repo.update_entry_status(user_id, status, admin_user_id if status == 'approved' else None)
        
        # Check if operation was successful
        if not result.get('success'):
            return jsonify(result), 400
            
        # Return the result
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error updating waiting list status: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500
