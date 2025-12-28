"""
User API

This module provides API endpoints for managing user information.
"""

import logging
from flask import Blueprint, request, jsonify, g

from server.utils.auth import require_auth
from server.utils.user_utils import get_current_user_id
from src.utils.user_repository import user_repo
from server.utils.usage_limiter import usage_limiter
# Import Firebase configuration
from server.config.firebase_config import firebase_auth, firebase_initialized

# Create blueprint
user_bp = Blueprint('user', __name__)

# Configure logging
logger = logging.getLogger('server.api.user')

@user_bp.route('/api/user/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Get current user information.
    If the user doesn't exist in the database, it will be created.

    Returns:
        JSON response with user information
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User not authenticated"
            }), 401

        # Get user information
        result = user_repo.get_user(user_id)

        # Check if operation was successful
        if not result.get('success'):
            return jsonify(result), 400

        limit_info = usage_limiter.get_monthly_limit_info(
            user_id=user_id,
            endpoints=['/api/stream', '/api/scholar-pk','/api/github/analyze','/api/github/compare','/api/linkedin/analyze','/api/linkedin/compare'],
            limit=5,
            days=30
        )
        # Return the result
        result['user']['remaining'] = limit_info['remaining']
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting user information: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@user_bp.route('/api/user/me', methods=['PUT', 'PATCH'])
@require_auth
def update_current_user():
    """
    Update current user information.

    Request body:
        display_name: User's display name (optional)
        email: User's email address (optional)
        profile_picture: URL to user's profile picture (optional)
        preferences: User preferences in JSON format (optional)

    Returns:
        JSON response with updated user information
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

        # Validate data
        allowed_fields = ["display_name", "email", "profile_picture", "preferences"]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}

        # Update user information
        result = user_repo.update_user(user_id, update_data)

        # Check if operation was successful
        if not result.get('success'):
            return jsonify(result), 400

        # Return the result
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error updating user information: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@user_bp.route('/api/user/firebase-info', methods=['GET'])
@require_auth
def get_firebase_user_info():
    """
    Get current user's Firebase information.

    Returns:
        JSON response with Firebase user information
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User not authenticated"
            }), 401

        # Check if Firebase is initialized
        if not firebase_initialized or not firebase_auth:
            return jsonify({
                "success": False,
                "error": "Firebase authentication service is not available"
            }), 503

        try:
            # Get user information from Firebase
            firebase_user = firebase_auth.get_user(user_id)

            # Extract user information
            user_info = {
                "uid": firebase_user.uid,
                "email": getattr(firebase_user, 'email', None),
                "email_verified": getattr(firebase_user, 'email_verified', False),
                "display_name": getattr(firebase_user, 'display_name', None),
                "photo_url": getattr(firebase_user, 'photo_url', None),
                "phone_number": getattr(firebase_user, 'phone_number', None),
                "disabled": getattr(firebase_user, 'disabled', False),
            }

            # Handle user metadata (creation and last sign in timestamps)
            user_metadata = getattr(firebase_user, 'user_metadata', None)
            if user_metadata:
                user_info['creation_timestamp'] = getattr(user_metadata, 'creation_timestamp', None)
                user_info['last_sign_in_timestamp'] = getattr(user_metadata, 'last_sign_in_timestamp', None)

            # Get provider data
            provider_data = getattr(firebase_user, 'provider_data', [])
            providers = []

            for provider in provider_data:
                provider_info = {
                    "provider_id": getattr(provider, 'provider_id', None),
                    "display_name": getattr(provider, 'display_name', None),
                    "email": getattr(provider, 'email', None),
                    "photo_url": getattr(provider, 'photo_url', None),
                }
                providers.append(provider_info)

            user_info['providers'] = providers

            # Get custom claims
            custom_claims = getattr(firebase_user, 'custom_claims', {}) or {}
            user_info['custom_claims'] = custom_claims

            # Get database user information
            db_user_result = user_repo.get_user(user_id)

            # Combine Firebase and database user information
            result = {
                "success": True,
                "firebase_user": user_info,
                "database_user": db_user_result.get('user') if db_user_result.get('success') else None
            }

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error getting Firebase user information: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"Failed to get Firebase user information: {str(e)}"
            }), 400

    except Exception as e:
        logger.error(f"Error in Firebase user info endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500
