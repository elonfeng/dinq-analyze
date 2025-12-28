"""
User Verification API

This module provides API endpoints for user verification system.
"""

import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify, g

# Import authentication utilities
from server.utils.auth import require_verified_user

# Import services
from server.services.user_verification_service import (
    user_verification_service,
    email_verification_service
)
from server.services.email_service import email_service

# Import models
from server.models.user_verification import (
    UserType,
    VerificationStep,
    JOB_SEEKER_STEP_SCHEMAS,
    RECRUITER_STEP_SCHEMAS
)

# Create blueprint
user_verification_bp = Blueprint('user_verification', __name__, url_prefix='/api/verification')

# Configure logging
logger = logging.getLogger(__name__)

def verification_to_dict(verification) -> Dict[str, Any]:
    """Convert UserVerification SQLAlchemy model to dictionary"""
    return {
        'id': verification.id,
        'user_id': verification.user_id,
        'user_type': verification.user_type,
        'current_step': verification.current_step,
        'verification_status': verification.verification_status,
        'full_name': verification.full_name,
        'avatar_url': verification.avatar_url,
        'current_role': verification.user_current_role,
        'current_title': verification.current_title,
        'research_fields': verification.research_fields,
        'university_name': verification.university_name,
        'degree_level': verification.degree_level,
        'department_major': verification.department_major,
        'edu_email': verification.edu_email,
        'edu_email_verified': verification.edu_email_verified,
        'education_documents': verification.education_documents,
        'job_title': verification.job_title,
        'company_org': verification.company_org,
        'work_research_summary': verification.work_research_summary,
        'company_email': verification.company_email,
        'company_email_verified': verification.company_email_verified,
        'professional_documents': verification.professional_documents,
        'company_name': verification.company_name,
        'industry': verification.industry,
        'company_website': verification.company_website,
        'company_introduction': verification.company_introduction,
        'recruiter_company_email': verification.recruiter_company_email,
        'recruiter_company_email_verified': verification.recruiter_company_email_verified,
        'company_documents': verification.company_documents,
        'github_username': verification.github_username,
        'github_verified': verification.github_verified,
        'linkedin_url': verification.linkedin_url,
        'linkedin_verified': verification.linkedin_verified,
        'twitter_username': verification.twitter_username,
        'twitter_verified': verification.twitter_verified,
        'google_scholar_url': verification.google_scholar_url,
        'google_scholar_verified': verification.google_scholar_verified,
        'created_at': verification.created_at.isoformat() if verification.created_at else None,
        'updated_at': verification.updated_at.isoformat() if verification.updated_at else None,
        'completed_at': verification.completed_at.isoformat() if verification.completed_at else None
    }

def validate_step_data(user_type: str, step: str, data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate step data according to schema

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Get schema based on user type
        if user_type == UserType.JOB_SEEKER.value:
            schemas = JOB_SEEKER_STEP_SCHEMAS
        elif user_type == UserType.RECRUITER.value:
            schemas = RECRUITER_STEP_SCHEMAS
        else:
            return False, f"Invalid user type: {user_type}"

        if step not in schemas:
            return False, f"Invalid step: {step}"

        schema = schemas[step]

        # Check required fields
        for field in schema['required']:
            if field not in data or not data[field]:
                return False, f"Required field missing: {field}"

        return True, ""
    except Exception as e:
        logger.error(f"Error validating step data: {e}")
        return False, f"Validation error: {str(e)}"

@user_verification_bp.route('/status', methods=['GET', 'OPTIONS'])
@require_verified_user
def get_verification_status():
    """Get current verification status for user"""
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        user_id = g.user_id
        logger.info(f"Getting verification status for user: {user_id}")

        # Get user verification record
        verification = user_verification_service.get_user_verification(user_id)

        if not verification:
            return jsonify({
                'success': True,
                'data': {
                    'exists': False,
                    'message': 'No verification record found. Please start verification process.'
                }
            }), 200

        # Get email verification statuses
        email_statuses = {}
        if verification.edu_email:
            email_statuses['edu_email'] = email_verification_service.is_email_verified(
                user_id, verification.edu_email, 'edu_email'
            )
        if verification.company_email:
            email_statuses['company_email'] = email_verification_service.is_email_verified(
                user_id, verification.company_email, 'company_email'
            )
        if verification.recruiter_company_email:
            email_statuses['recruiter_company_email'] = email_verification_service.is_email_verified(
                user_id, verification.recruiter_company_email, 'recruiter_company_email'
            )

        # Convert SQLAlchemy model to dict
        verification_data = verification_to_dict(verification)
        verification_data['email_verification_statuses'] = email_statuses

        return jsonify({
            'success': True,
            'data': {
                'exists': True,
                'verification': verification_data
            }
        }), 200

    except Exception as e:
        logger.error(f"Error getting verification status: {e}")
        return jsonify({
            'error': f'Failed to get verification status: {str(e)}',
            'success': False
        }), 500

@user_verification_bp.route('/start', methods=['POST', 'OPTIONS'])
@require_verified_user
def start_verification():
    """Start verification process"""
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        user_id = g.user_id
        data = request.get_json()

        if not data:
            return jsonify({
                'error': 'No JSON data provided',
                'success': False
            }), 400

        user_type = data.get('user_type')
        if user_type not in [UserType.JOB_SEEKER.value, UserType.RECRUITER.value]:
            return jsonify({
                'error': f'Invalid user type. Must be one of: {[t.value for t in UserType]}',
                'success': False
            }), 400

        logger.info(f"Starting verification for user {user_id} as {user_type}")

        # Check if verification already exists
        existing_verification = user_verification_service.get_user_verification(user_id)
        if existing_verification:
            return jsonify({
                'success': True,
                'data': {
                    'verification': verification_to_dict(existing_verification),
                    'message': 'Verification already exists. You can continue from where you left off.'
                }
            }), 200

        # Create new verification record
        verification = user_verification_service.create_user_verification(user_id, user_type)

        return jsonify({
            'success': True,
            'data': {
                'verification': verification_to_dict(verification),
                'message': 'Verification process started successfully.'
            }
        }), 201

    except Exception as e:
        logger.error(f"Error starting verification: {e}")
        return jsonify({
            'error': f'Failed to start verification: {str(e)}',
            'success': False
        }), 500

@user_verification_bp.route('/update-step', methods=['POST', 'OPTIONS'])
@require_verified_user
def update_step():
    """Update verification step data"""
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        user_id = g.user_id
        data = request.get_json()

        if not data:
            return jsonify({
                'error': 'No JSON data provided',
                'success': False
            }), 400

        step = data.get('step')
        step_data = data.get('data', {})
        advance_to_next = data.get('advance_to_next', False)

        logger.info(f"Updating step {step} for user {user_id}")

        # Get current verification
        verification = user_verification_service.get_user_verification(user_id)
        if not verification:
            return jsonify({
                'error': 'No verification record found. Please start verification first.',
                'success': False
            }), 404

        # Validate step data
        is_valid, error_message = validate_step_data(verification.user_type, step, step_data)
        if not is_valid:
            return jsonify({
                'error': f'Validation failed: {error_message}',
                'success': False
            }), 400

        # Update verification record
        updated_verification = user_verification_service.update_user_verification(user_id, step_data)

        # Advance to next step if requested
        if advance_to_next:
            next_step = get_next_step(verification.user_type, step)
            if next_step:
                updated_verification = user_verification_service.advance_step(user_id, next_step)
            elif step == get_final_step(verification.user_type):
                # Complete verification if this is the final step
                updated_verification = user_verification_service.complete_verification(user_id)

                # Send welcome email
                try:
                    email_service.send_welcome_email(
                        to_email=updated_verification.edu_email or updated_verification.company_email or updated_verification.recruiter_company_email,
                        user_name=updated_verification.full_name,
                        user_type=updated_verification.user_type
                    )
                except Exception as email_error:
                    logger.error(f"Failed to send welcome email: {email_error}")

        return jsonify({
            'success': True,
            'data': {
                'verification': verification_to_dict(updated_verification),
                'message': 'Step updated successfully.'
            }
        }), 200

    except Exception as e:
        logger.error(f"Error updating step: {e}")
        return jsonify({
            'error': f'Failed to update step: {str(e)}',
            'success': False
        }), 500

@user_verification_bp.route('/send-email-verification', methods=['POST', 'OPTIONS'])
@require_verified_user
def send_email_verification():
    """Send email verification code"""
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        user_id = g.user_id
        data = request.get_json()

        if not data:
            return jsonify({
                'error': 'No JSON data provided',
                'success': False
            }), 400

        email = data.get('email')
        email_type = data.get('email_type')  # 'edu_email', 'company_email', 'recruiter_company_email'

        if not email or not email_type:
            return jsonify({
                'error': 'Email and email_type are required',
                'success': False
            }), 400

        # if email_type not in ['edu_email', 'company_email', 'recruiter_company_email']:
        #     return jsonify({
        #         'error': 'Invalid email_type',
        #         'success': False
        #     }), 400

        logger.info(f"Sending email verification to {email} for user {user_id}")

        # Get user verification for name
        verification = user_verification_service.get_user_verification(user_id)
        user_name = verification.full_name if verification else None

        # Generate verification code
        verification_code = email_verification_service.create_verification_code(
            user_id, email, email_type
        )

        # Send email
        email_sent = email_service.send_verification_email(
            to_email=email,
            verification_code=verification_code,
            email_type=email_type,
            user_name=user_name,
            user_id=user_id
        )

        if email_sent:
            return jsonify({
                'success': True,
                'data': {
                    'message': 'Verification email sent successfully.',
                    'email': email,
                    'email_type': email_type
                }
            }), 200
        else:
            return jsonify({
                'error': 'Failed to send verification email',
                'success': False
            }), 500

    except Exception as e:
        logger.error(f"Error sending email verification: {e}")
        return jsonify({
            'error': f'Failed to send email verification: {str(e)}',
            'success': False
        }), 500

@user_verification_bp.route('/verify-email', methods=['POST', 'OPTIONS'])
@require_verified_user
def verify_email():
    """Verify email with verification code"""
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        user_id = g.user_id
        data = request.get_json()

        if not data:
            return jsonify({
                'error': 'No JSON data provided',
                'success': False
            }), 400

        email = data.get('email')
        email_type = data.get('email_type')
        verification_code = data.get('verification_code')

        if not all([email, email_type, verification_code]):
            return jsonify({
                'error': 'Email, email_type, and verification_code are required',
                'success': False
            }), 400

        logger.info(f"Verifying email {email} for user {user_id}")

        # Verify the code
        is_verified = email_verification_service.verify_code(
            user_id, email, email_type, verification_code
        )

        if is_verified:
            # Update verification record
            update_data = {f"{email_type}_verified": True}
            user_verification_service.update_user_verification(user_id, update_data)

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
            return jsonify({
                'error': 'Invalid or expired verification code',
                'success': False
            }), 400

    except Exception as e:
        logger.error(f"Error verifying email: {e}")
        return jsonify({
            'error': f'Failed to verify email: {str(e)}',
            'success': False
        }), 500

@user_verification_bp.route('/complete', methods=['POST', 'OPTIONS'])
@require_verified_user
def complete_verification():
    """Complete verification process"""
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        user_id = g.user_id
        logger.info(f"Completing verification for user {user_id}")

        # Get current verification
        verification = user_verification_service.get_user_verification(user_id)
        if not verification:
            return jsonify({
                'error': 'No verification record found',
                'success': False
            }), 404

        # Complete verification
        completed_verification = user_verification_service.complete_verification(user_id)

        # Send welcome email
        try:
            primary_email = (
                completed_verification.edu_email or
                completed_verification.company_email or
                completed_verification.recruiter_company_email
            )

            if primary_email:
                email_service.send_welcome_email(
                    to_email=primary_email,
                    user_name=completed_verification.full_name,
                    user_type=completed_verification.user_type
                )
        except Exception as email_error:
            logger.error(f"Failed to send welcome email: {email_error}")

        return jsonify({
            'success': True,
            'data': {
                'verification': verification_to_dict(completed_verification),
                'message': 'Verification completed successfully!'
            }
        }), 200

    except Exception as e:
        logger.error(f"Error completing verification: {e}")
        return jsonify({
            'error': f'Failed to complete verification: {str(e)}',
            'success': False
        }), 500

@user_verification_bp.route('/stats', methods=['GET', 'OPTIONS'])
def get_verification_stats():
    """Get verification statistics (admin endpoint)"""
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        stats = user_verification_service.get_verification_stats()

        return jsonify({
            'success': True,
            'data': stats
        }), 200

    except Exception as e:
        logger.error(f"Error getting verification stats: {e}")
        return jsonify({
            'error': f'Failed to get verification stats: {str(e)}',
            'success': False
        }), 500

def get_next_step(user_type: str, current_step: str) -> str:
    """Get next step in verification process"""
    if user_type == UserType.JOB_SEEKER.value:
        steps = ['basic_info', 'education', 'professional', 'social_accounts']
    else:  # recruiter
        steps = ['basic_info', 'company_org', 'social_accounts']

    try:
        current_index = steps.index(current_step)
        if current_index < len(steps) - 1:
            return steps[current_index + 1]
    except ValueError:
        pass

    return None

def get_final_step(user_type: str) -> str:
    """Get final step in verification process"""
    if user_type == UserType.JOB_SEEKER.value:
        return 'social_accounts'
    else:  # recruiter
        return 'social_accounts'
