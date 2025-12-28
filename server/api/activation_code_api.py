"""
Activation Code API

This module provides API endpoints for managing activation codes.
"""

import logging
from flask import Blueprint, request, jsonify, g

from server.utils.auth import require_verified_user, require_auth
from server.utils.user_utils import get_current_user_id
from src.utils.activation_code_repository import activation_code_repo
from src.utils.user_repository import user_repo

# Create blueprint
activation_code_bp = Blueprint('activation_code', __name__)

# Configure logging
logger = logging.getLogger('server.api.activation_code')

@activation_code_bp.route('/api/activation-codes/create', methods=['POST'])
@require_verified_user
def create_activation_code():
    """
    Create a new activation code.

    Request body:
        expires_in_days: Number of days until the code expires (optional)
        batch_id: Batch identifier for bulk code generation (optional)
        notes: Additional notes or purpose of this code (optional)

    Returns:
        JSON response with the created activation code
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

        # Extract parameters
        expires_in_days = data.get('expires_in_days')
        batch_id = data.get('batch_id')
        notes = data.get('notes')

        # Validate expires_in_days if provided
        if expires_in_days is not None:
            try:
                expires_in_days = int(expires_in_days)
                if expires_in_days < 0:
                    return jsonify({
                        "success": False,
                        "error": "expires_in_days must be a positive integer"
                    }), 400
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": "expires_in_days must be a valid integer"
                }), 400

        # Create activation code
        result = activation_code_repo.create_code(
            created_by=user_id,
            expires_in_days=expires_in_days,
            batch_id=batch_id,
            notes=notes
        )

        # Check if creation was successful
        if not result.get('success'):
            return jsonify(result), 400

        # Return the created code
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error creating activation code: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@activation_code_bp.route('/api/activation-codes/use', methods=['POST'])
@require_auth
def use_activation_code():
    """
    Use an activation code.

    Request body:
        code: The activation code to use

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

        # Extract code
        code = data.get('code')
        if not code:
            return jsonify({
                "success": False,
                "error": "Activation code is required"
            }), 400

        # Use the code
        result = activation_code_repo.use_code(code, user_id)

        # Check if operation was successful
        if not result.get('success'):
            return jsonify(result), 400

        # Update user activation status
        user_result = user_repo.update_user_activation(user_id, code)

        # Combine results
        combined_result = {
            "success": True,
            "message": result.get('message', 'Activation code used successfully'),
            "code": result.get('code'),
            "used_at": result.get('used_at'),
            "user": user_result.get('user') if user_result.get('success') else None
        }

        # Return the combined result
        return jsonify(combined_result)

    except Exception as e:
        logger.error(f"Error using activation code: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@activation_code_bp.route('/api/activation-codes/verify', methods=['GET', 'POST'])
@require_auth
def verify_activation_code():
    """
    Verify if an activation code is valid.

    Query parameters (GET) or request body (POST):
        code: The activation code to verify

    Returns:
        JSON response with the verification result
    """
    try:
        # Get code from query parameters or request body
        code = None
        if request.method == 'GET':
            code = request.args.get('code')
        else:  # POST
            data = request.get_json() or {}
            code = data.get('code')

        if not code:
            return jsonify({
                "success": False,
                "error": "Activation code is required"
            }), 400

        # Verify the code
        result = activation_code_repo.verify_code(code)

        # Return the result
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error verifying activation code: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@activation_code_bp.route('/api/activation-codes', methods=['GET'])
@require_verified_user
def get_activation_codes():
    """
    Get activation codes with optional filtering.

    Query parameters:
        is_used: Filter by usage status (true/false)
        batch_id: Filter by batch ID
        limit: Maximum number of codes to return (default: 100)
        offset: Offset for pagination (default: 0)

    Returns:
        JSON response with a list of activation codes
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User not authenticated"
            }), 401

        # Extract query parameters
        is_used_str = request.args.get('is_used')
        batch_id = request.args.get('batch_id')

        # Parse is_used parameter
        is_used = None
        if is_used_str is not None:
            is_used = is_used_str.lower() == 'true'

        # Parse pagination parameters
        try:
            limit = min(100, max(1, int(request.args.get('limit', 100))))
        except ValueError:
            limit = 100

        try:
            offset = max(0, int(request.args.get('offset', 0)))
        except ValueError:
            offset = 0

        # Get activation codes
        result = activation_code_repo.get_codes(
            user_id=user_id,
            is_used=is_used,
            batch_id=batch_id,
            limit=limit,
            offset=offset
        )

        # Return the result
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting activation codes: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500


@activation_code_bp.route('/api/activation-codes/batch-create', methods=['POST'])
@require_verified_user
def batch_create_activation_codes():
    """
    Batch create activation codes.
    Request body:
        count: Number of codes to create (required)
        expires_in_days: Number of days until the codes expire (optional)
        batch_id: Batch identifier for bulk code generation (optional)
        notes: Additional notes or purpose of these codes (optional)
    Returns:
        JSON response with the created activation codes
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

        # Extract parameters
        count = data.get('count')
        expires_in_days = data.get('expires_in_days')
        batch_id = data.get('batch_id')
        notes = data.get('notes')

        # Validate count
        if not count or not isinstance(count, int) or count <= 0:
            return jsonify({
                "success": False,
                "error": "count must be a positive integer"
            }), 400

        if count > 100:
            return jsonify({
                "success": False,
                "error": "Cannot create more than 100 codes at once"
            }), 400

        # Validate expires_in_days if provided
        if expires_in_days is not None:
            try:
                expires_in_days = int(expires_in_days)
                if expires_in_days < 0:
                    return jsonify({
                        "success": False,
                        "error": "expires_in_days must be a positive integer"
                    }), 400
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": "expires_in_days must be a valid integer"
                }), 400

        # Create activation codes
        codes = []
        for _ in range(count):
            result = activation_code_repo.create_code(
                created_by=user_id,
                expires_in_days=expires_in_days,
                batch_id=batch_id,
                notes=notes
            )

            if not result.get('success'):
                return jsonify(result), 400

            codes.append(result)

        # Return the created codes
        return jsonify({
            "success": True,
            "count": len(codes),
            "codes": codes
        })

    except Exception as e:
        logger.error(f"Error batch creating activation codes: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@activation_code_bp.route('/api/activation-codes/admin', methods=['GET'])
def admin_get_activation_codes():
    """
    Get activation codes with optional filtering (admin version).
    This endpoint does not require user_id filtering.
    Query parameters:
        is_used: Filter by usage status (true/false)
        batch_id: Filter by batch ID
        search: Search in code, batch_id, or notes
        limit: Maximum number of codes to return (default: 100)
        offset: Offset for pagination (default: 0)
    Returns:
        JSON response with a list of activation codes
    """
    try:
        # Extract query parameters
        is_used_str = request.args.get('is_used')
        batch_id = request.args.get('batch_id')

        # Parse is_used parameter
        is_used = None
        if is_used_str is not None:
            is_used = is_used_str.lower() == 'true'

        # Parse pagination parameters
        try:
            limit = min(100, max(1, int(request.args.get('limit', 100))))
        except ValueError:
            limit = 100

        try:
            offset = max(0, int(request.args.get('offset', 0)))
        except ValueError:
            offset = 0

        # Get activation codes
        result = activation_code_repo.get_codes(
            is_used=is_used,
            batch_id=batch_id,
            limit=limit,
            offset=offset
        )

        # Return the result
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting activation codes: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500