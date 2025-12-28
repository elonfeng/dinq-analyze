"""
Email Verification Page API

This module provides the web page for email verification via link.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import logging
from server.services.user_verification_service import email_verification_service

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
email_verification_page_bp = Blueprint('email_verification_page', __name__)

@email_verification_page_bp.route('/verify-email', methods=['GET'])
def verify_email_page():
    """
    Display email verification page
    
    URL Parameters:
        - code: verification code
        - email: email address
        - type: email type (edu_email, company_email, etc.)
        - user_id: user ID (optional)
    """
    try:
        # Get parameters from URL
        code = request.args.get('code')
        email = request.args.get('email')
        email_type = request.args.get('type')
        user_id = request.args.get('user_id')
        
        logger.info(f"Email verification page accessed: email={email}, type={email_type}, code={code[:3]}***")
        
        # Render the verification page
        return render_template('verify_email.html')
        
    except Exception as e:
        logger.error(f"Error displaying email verification page: {e}")
        return render_template('verify_email.html'), 500

@email_verification_page_bp.route('/api/verify-email-link', methods=['POST'])
def verify_email_link():
    """
    API endpoint for verifying email via link (without authentication)
    
    This endpoint is used by the verification page to verify emails
    when users click the link in their email.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        email = data.get('email')
        email_type = data.get('email_type')
        verification_code = data.get('verification_code')
        user_id = data.get('user_id')
        
        # Validate required fields
        if not all([email, email_type, verification_code]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: email, email_type, verification_code'
            }), 400
        
        logger.info(f"Verifying email via link: {email} (type: {email_type}) for user {user_id}")
        
        # If user_id is provided, use it; otherwise try to find the verification record
        if user_id:
            # Verify with specific user_id
            is_verified = email_verification_service.verify_code(
                user_id, email, email_type, verification_code
            )
        else:
            # Try to find verification record by email and code
            is_verified = email_verification_service.verify_code_by_email(
                email, email_type, verification_code
            )
        
        if is_verified:
            logger.info(f"Email verification successful: {email}")
            return jsonify({
                'success': True,
                'data': {
                    'message': 'Email verified successfully.',
                    'email': email,
                    'email_type': email_type,
                    'verified': True
                }
            }), 200
        else:
            logger.warning(f"Email verification failed: {email}")
            return jsonify({
                'success': False,
                'error': 'Invalid or expired verification code'
            }), 400
            
    except Exception as e:
        logger.error(f"Error in email verification via link: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
