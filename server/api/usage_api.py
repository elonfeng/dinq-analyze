"""
API Usage API

This module provides API endpoints for users to query their own API usage statistics.
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func, cast, Date
from typing import Dict, Any, List, Optional

from server.utils.auth import require_verified_user
from server.utils.user_utils import get_current_user_id
from src.models.db import ApiUsage
from src.utils.db_utils import get_db_session

# Create blueprint
usage_api_bp = Blueprint('usage_api', __name__)

# Configure logging
logger = logging.getLogger('server.api.usage')

@usage_api_bp.route('/api/usage/stats', methods=['GET'])
@require_verified_user
def get_user_usage_stats():
    """
    Get the current user's API usage statistics.

    Query parameters:
        days: Number of days to look back (default: 3, max: 30)
        include_recent: Whether to include recent calls (default: false)
        include_endpoints: Whether to include endpoint statistics (default: false)

    Returns:
        JSON response with API usage statistics
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User not authenticated"
            }), 401

        # Get days parameter (default: 3, max: 30)
        try:
            days = int(request.args.get('days', 3))
            # Limit to reasonable range
            days = max(1, min(days, 30))  # Between 1 and 30 days
        except ValueError:
            days = 3

        # Get optional parameters
        include_recent = request.args.get('include_recent', 'false').lower() == 'true'
        include_endpoints = request.args.get('include_endpoints', 'false').lower() == 'true'

        # Calculate start date
        start_date = datetime.now() - timedelta(days=days)

        with get_db_session() as session:
            # Get total API calls (always included)
            total_calls = session.query(ApiUsage).filter(
                ApiUsage.user_id == user_id,
                ApiUsage.created_at >= start_date
            ).count()

            # Prepare response data
            response_data = {
                "total_calls": total_calls,
                "days": days
            }

            # Get API calls by endpoint (optional)
            if include_endpoints:
                endpoint_stats = session.query(
                    ApiUsage.endpoint,
                    func.count(ApiUsage.id).label('count')
                ).filter(
                    ApiUsage.user_id == user_id,
                    ApiUsage.created_at >= start_date
                ).group_by(ApiUsage.endpoint).all()

                # Format endpoint stats
                endpoint_data = [
                    {"endpoint": endpoint, "count": count}
                    for endpoint, count in endpoint_stats
                ]

                response_data["endpoints"] = endpoint_data

            # Get daily API usage (always included)
            daily_stats = session.query(
                cast(ApiUsage.created_at, Date).label('date'),
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.user_id == user_id,
                ApiUsage.created_at >= start_date
            ).group_by('date').order_by('date').all()

            # Format daily stats
            daily_data = [
                {"date": date.isoformat(), "count": count}
                for date, count in daily_stats
            ]

            response_data["daily_usage"] = daily_data

            # Get recent API calls (optional)
            if include_recent:
                recent_calls = session.query(ApiUsage).filter(
                    ApiUsage.user_id == user_id
                ).order_by(ApiUsage.created_at.desc()).limit(10).all()

                # Format recent calls
                recent_data = []
                for call in recent_calls:
                    recent_data.append({
                        "id": call.id,
                        "endpoint": call.endpoint,
                        "query": call.query,
                        "query_type": call.query_type,
                        "scholar_id": call.scholar_id,
                        "status": call.status,
                        "execution_time": call.execution_time,
                        "created_at": call.created_at.isoformat() if call.created_at else None
                    })

                response_data["recent_calls"] = recent_data

            return jsonify({
                "success": True,
                "data": response_data
            })

    except Exception as e:
        logger.error(f"Error retrieving API usage stats: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500

@usage_api_bp.route('/api/usage/details', methods=['GET'])
@require_verified_user
def get_user_usage_details():
    """
    Get detailed information about the current user's API usage.

    Query parameters:
        endpoint: Filter by specific endpoint (optional)
        start_date: Start date in ISO format (YYYY-MM-DD) (optional, default: 3 days ago)
        end_date: End date in ISO format (YYYY-MM-DD) (optional, default: today)
        page: Page number for pagination (default: 1)
        per_page: Number of items per page (default: 10, max: 50)

    Returns:
        JSON response with detailed API usage information
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                "success": False,
                "error": "User not authenticated"
            }), 401

        # Get query parameters
        endpoint = request.args.get('endpoint')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # Parse pagination parameters
        try:
            page = max(1, int(request.args.get('page', 1)))
        except ValueError:
            page = 1

        try:
            per_page = min(50, max(1, int(request.args.get('per_page', 10))))
        except ValueError:
            per_page = 10

        # Parse dates
        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                # Default to 3 days ago if invalid
                start_date = datetime.now() - timedelta(days=3)
        else:
            # Default to 3 days ago
            start_date = datetime.now() - timedelta(days=3)

        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
                # Set time to end of day
                end_date = end_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                # Default to now if invalid
                end_date = datetime.now()
        else:
            # Default to now
            end_date = datetime.now()

        # Ensure the date range doesn't exceed 30 days
        date_diff = (end_date - start_date).days
        if date_diff > 30:
            # Adjust start_date to be 30 days before end_date
            start_date = end_date - timedelta(days=30)
            logger.info(f"Date range exceeded 30 days, adjusted to 30 days from {start_date.isoformat()} to {end_date.isoformat()}")

        with get_db_session() as session:
            # Build query
            query = session.query(ApiUsage).filter(
                ApiUsage.user_id == user_id,
                ApiUsage.created_at >= start_date,
                ApiUsage.created_at <= end_date
            )

            # Apply endpoint filter if provided
            if endpoint:
                query = query.filter(ApiUsage.endpoint == endpoint)

            # Get total count for pagination
            total_count = query.count()

            # Apply pagination
            offset = (page - 1) * per_page
            query = query.order_by(ApiUsage.created_at.desc()).offset(offset).limit(per_page)

            # Execute query
            usage_records = query.all()

            # Format results - simplified to include only essential fields
            results = []
            for record in usage_records:
                results.append({
                    "id": record.id,
                    "endpoint": record.endpoint,
                    "query": record.query,
                    "status": record.status,
                    "execution_time": record.execution_time,
                    "created_at": record.created_at.isoformat() if record.created_at else None
                })

            # Prepare pagination info
            total_pages = (total_count + per_page - 1) // per_page  # Ceiling division

            # Prepare response data
            response_data = {
                "records": results,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": total_pages
                },
                "filters": {
                    "endpoint": endpoint,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }

            return jsonify({
                "success": True,
                "data": response_data
            })

    except Exception as e:
        logger.error(f"Error retrieving API usage details: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500
