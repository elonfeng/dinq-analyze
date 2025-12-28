"""
Demo Request API

This module provides API endpoints for handling demo requests from users
interested in the product.
"""

import logging
from flask import Blueprint, request, jsonify, g
from datetime import datetime

from server.utils.auth import require_verified_user
from server.utils.user_utils import get_current_user_id
from src.utils.user_interactions_repository import demo_request_repo
from src.models.user_interactions import DemoRequest
from src.utils.db_utils import get_db_session

# Create blueprint
demo_request_bp = Blueprint('demo_request', __name__)

# Configure logging
logger = logging.getLogger(__name__)

@demo_request_bp.route('/api/demo-request', methods=['POST'])
@require_verified_user
def submit_demo_request():
    """
    Submit a new demo request.

    Required fields:
    - email: Email address for contact
    - affiliation: Organization or institution
    - country: Country of the requester
    - job_title: Job title of the requester
    - contact_reason: Reason for requesting a demo

    Optional fields:
    - additional_details: Additional details about the request
    - marketing_consent: Whether the user consents to marketing communications

    Returns:
        JSON response with success status
    """
    try:
        # Get current user ID
        # 打印所有请求头
        
        user_id = get_current_user_id()
        # Get request data
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400

        # Validate required fields
        required_fields = ['email', 'affiliation', 'country', 'job_title', 'contact_reason']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return jsonify({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400

        # Create demo request directly using the session
        try:
            with get_db_session() as session:
                # Create the demo request object
                demo_request = DemoRequest(
                    user_id=user_id,
                    email=data.get('email'),
                    affiliation=data.get('affiliation'),
                    country=data.get('country'),
                    job_title=data.get('job_title'),
                    contact_reason=data.get('contact_reason'),
                    additional_details=data.get('additional_details'),
                    marketing_consent=data.get('marketing_consent', False),
                    status="pending",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )

                # Add to session
                session.add(demo_request)
                session.commit()

                # Convert to dictionary for response
                result = {
                    'id': demo_request.id,
                    'user_id': demo_request.user_id,
                    'email': demo_request.email,
                    'affiliation': demo_request.affiliation,
                    'country': demo_request.country,
                    'job_title': demo_request.job_title,
                    'contact_reason': demo_request.contact_reason,
                    'additional_details': demo_request.additional_details,
                    'marketing_consent': demo_request.marketing_consent,
                    'status': demo_request.status,
                    'created_at': demo_request.created_at.isoformat() if demo_request.created_at else None,
                    'updated_at': demo_request.updated_at.isoformat() if demo_request.updated_at else None
                }

                logger.info(f"Created demo request with ID: {demo_request.id} for user: {user_id}")

                return jsonify({
                    'success': True,
                    'message': 'Demo request submitted successfully',
                    'data': result
                })
        except Exception as e:
            logger.error(f"Database error creating demo request: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Database error: {str(e)}'
            }), 500
    except Exception as e:
        logger.error(f"Error submitting demo request: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@demo_request_bp.route('/api/demo-request/my-requests', methods=['GET'])
@require_verified_user
def get_my_demo_requests():
    """
    Get all demo requests submitted by the current user.

    Returns:
        JSON response with the user's demo requests
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()

        # Get user's demo requests
        requests = demo_request_repo.get_user_demo_requests(user_id)

        return jsonify({
            'success': True,
            'data': {
                'requests': requests
            }
        })
    except Exception as e:
        logger.error(f"Error getting user demo requests: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@demo_request_bp.route('/api/admin/demo-requests', methods=['GET'])
def get_demo_requests_admin():
    """
    Get all demo requests with filtering and pagination for admin dashboard.
    
    Query Parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 10)
    - status: Filter by status (pending, contacted, completed)
    - search: Search in email, affiliation, or additional_details
    - sort_by: Field to sort by (created_at, status, etc.)
    - sort_order: Sort order (asc, desc)
    
    Returns:
        JSON response with paginated demo requests
    """
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        status = request.args.get('status')
        search = request.args.get('search', '')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')

        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 10

        # Get demo requests with filtering and pagination
        with get_db_session() as session:
            query = session.query(DemoRequest)

            # Apply filters
            if status:
                query = query.filter(DemoRequest.status == status)
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    (DemoRequest.email.ilike(search_term)) |
                    (DemoRequest.affiliation.ilike(search_term)) |
                    (DemoRequest.additional_details.ilike(search_term))
                )

            # Apply sorting
            if sort_order == 'desc':
                query = query.order_by(getattr(DemoRequest, sort_by).desc())
            else:
                query = query.order_by(getattr(DemoRequest, sort_by).asc())

            # Get total count
            total = query.count()

            # Apply pagination
            requests = query.offset((page - 1) * per_page).limit(per_page).all()

            # Convert to dictionaries
            results = []
            for req in requests:
                result = {
                    'id': req.id,
                    'user_id': req.user_id,
                    'email': req.email,
                    'affiliation': req.affiliation,
                    'country': req.country,
                    'job_title': req.job_title,
                    'contact_reason': req.contact_reason,
                    'additional_details': req.additional_details,
                    'marketing_consent': req.marketing_consent,
                    'status': req.status,
                    'created_at': req.created_at.isoformat() if req.created_at else None,
                    'updated_at': req.updated_at.isoformat() if req.updated_at else None
                }
                results.append(result)

            return jsonify({
                'success': True,
                'data': {
                    'requests': results,
                    'pagination': {
                        'total': total,
                        'page': page,
                        'per_page': per_page,
                        'total_pages': (total + per_page - 1) // per_page
                    }
                }
            })
    except Exception as e:
        logger.error(f"Error getting demo requests for admin: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@demo_request_bp.route('/api/admin/demo-requests/update', methods=['POST'])
def update_demo_request():
    """
    Update a demo request with provided fields.
    
    Request body:
        request_id: ID of the demo request to update (required)
        Any fields to update (email, affiliation, country, job_title, contact_reason, 
        additional_details, marketing_consent, status)
        
    Returns:
        JSON response with updated demo request
    """
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'message': 'No update data provided'
            }), 400

        # Validate required fields
        request_id = data.get('request_id')
        if not request_id:
            return jsonify({
                'success': False,
                'message': 'request_id is required'
            }), 400

        # Validate status if provided
        if 'status' in data and data['status'] not in ['pending', 'contacted', 'completed']:
            return jsonify({
                'success': False,
                'message': 'Invalid status'
            }), 400

        with get_db_session() as session:
            demo_request = session.query(DemoRequest).filter(DemoRequest.id == request_id).first()
            if not demo_request:
                return jsonify({
                    'success': False,
                    'message': 'Demo request not found'
                }), 404

            # Update only provided fields
            updateable_fields = [
                'email', 'affiliation', 'country', 'job_title', 
                'contact_reason', 'additional_details', 
                'marketing_consent', 'status'
            ]

            for field in updateable_fields:
                if field in data:
                    setattr(demo_request, field, data[field])

            demo_request.updated_at = datetime.now()
            session.commit()

            # Convert to dictionary for response
            result = {
                'id': demo_request.id,
                'user_id': demo_request.user_id,
                'email': demo_request.email,
                'affiliation': demo_request.affiliation,
                'country': demo_request.country,
                'job_title': demo_request.job_title,
                'contact_reason': demo_request.contact_reason,
                'additional_details': demo_request.additional_details,
                'marketing_consent': demo_request.marketing_consent,
                'status': demo_request.status,
                'created_at': demo_request.created_at.isoformat() if demo_request.created_at else None,
                'updated_at': demo_request.updated_at.isoformat() if demo_request.updated_at else None
            }

            return jsonify({
                'success': True,
                'message': 'Demo request updated successfully',
                'data': result
            })
    except Exception as e:
        logger.error(f"Error updating demo request: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500
