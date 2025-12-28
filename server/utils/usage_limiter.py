"""
Usage Limiter

This module provides functionality to limit API usage based on various criteria.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from src.utils.api_usage_repository import api_usage_repo
from src.utils.user_repository import user_repo

# Set up logger
logger = logging.getLogger('server.utils.usage_limiter')

class UsageLimiter:
    """
    Class for checking and enforcing usage limits on API endpoints.
    """

    @staticmethod
    def check_monthly_limit(user_id: str, endpoints: List[str], limit: int = 5, days: int = 30) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a user has exceeded their monthly usage limit for specified endpoints.
        Users who have activated their account with an activation code are not subject to limits.

        Args:
            user_id: ID of the user
            endpoints: List of API endpoints to check
            limit: Maximum number of calls allowed in the period
            days: Number of days to look back (default: 30)

        Returns:
            Tuple of (is_allowed, limit_info)
            - is_allowed: True if the user has NOT exceeded their limit or is activated, False otherwise
            - limit_info: Dictionary with information about the limit check
        """
        try:
            # First, check if the user has activated their account
            user_result = user_repo.get_user(user_id)

            # If user is activated, they are not subject to limits
            if user_result.get('success') and user_result.get('user', {}).get('is_activated', False):
                logger.info(f"User {user_id} is activated and not subject to usage limits")
                return True, {
                    "is_allowed": True,
                    "is_activated": True,
                    "total_usage": 0,  # Not relevant for activated users
                    "limit": None,     # No limit for activated users
                    "remaining": None, # No limit for activated users
                    "period_days": days,
                    "endpoint_counts": {},
                    "message": "Activated users are not subject to usage limits"
                }

            # For non-activated users, check usage counts
            endpoint_counts = {}
            total_count = 0

            for endpoint in endpoints:
                # Get usage count for this endpoint
                with_endpoint = api_usage_repo.get_endpoint_usage_count(user_id, endpoint, days)
                endpoint_counts[endpoint] = with_endpoint
                total_count += with_endpoint

            # Check if the total count exceeds the limit
            is_allowed = total_count < limit
            remaining = max(0, limit - total_count)

            # Prepare limit information
            limit_info = {
                "is_allowed": is_allowed,
                "is_activated": False,
                "total_usage": total_count,
                "limit": limit,
                "remaining": remaining,
                "period_days": days,
                "endpoint_counts": endpoint_counts
            }

            if not is_allowed:
                logger.warning(f"User {user_id} has exceeded their monthly limit for endpoints {endpoints}. "
                              f"Usage: {total_count}/{limit}")

            return is_allowed, limit_info

        except Exception as e:
            logger.error(f"Error checking monthly limit: {str(e)}")
            # In case of error, allow the request to proceed
            return True, {
                "is_allowed": True,
                "error": str(e),
                "limit": limit,
                "period_days": days
            }

    @staticmethod
    def get_limit_response(limit_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a standardized response for limit exceeded situations.

        Args:
            limit_info: Dictionary with information about the limit check

        Returns:
            Dictionary with response information
        """
        # Check if user is activated
        if limit_info.get("is_activated", False):
            # This should not happen, as activated users are not subject to limits
            return {
                "success": True,
                "message": "Activated users are not subject to usage limits",
                "limit_info": {
                    "is_activated": True,
                    "total_usage": limit_info.get("total_usage", 0),
                    "limit": None,
                    "remaining": None,
                    "period_days": limit_info.get("period_days", 30),
                    "endpoint_counts": limit_info.get("endpoint_counts", {})
                }
            }

        # For non-activated users who have exceeded their limit
        return {
            "success": False,
            "error": "Usage limit exceeded",
            "message": f"You have reached your limit of {limit_info['limit']} requests in the last {limit_info['period_days']} days. Please activate your account to remove this limit.",
            "limit_info": {
                "is_activated": False,
                "total_usage": limit_info.get("total_usage", 0),
                "limit": limit_info.get("limit", 0),
                "remaining": limit_info.get("remaining", 0),
                "period_days": limit_info.get("period_days", 30),
                "endpoint_counts": limit_info.get("endpoint_counts", {})
            }
        }

    @staticmethod
    def get_monthly_limit_info(user_id: str, endpoints: List[str], limit: int = 5, days: int = 30) -> Dict[str, Any]:
        """
        Get monthly usage limit information for a user without enforcing limits.
        This method only queries and returns limit information.

        Args:
            user_id: ID of the user
            endpoints: List of API endpoints to check
            limit: Maximum number of calls allowed in the period
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with information about the limit status
        """
        try:
            # First, check if the user has activated their account
            user_result = user_repo.get_user(user_id)

            # If user is activated, they are not subject to limits
            if user_result.get('success') and user_result.get('user', {}).get('is_activated', False):
                logger.info(f"User {user_id} is activated and not subject to usage limits")
                return {
                    "is_allowed": True,
                    "is_activated": True,
                    "total_usage": 0,  # Not relevant for activated users
                    "limit": None,     # No limit for activated users
                    "remaining": None, # No limit for activated users
                    "period_days": days,
                    "endpoint_counts": {},
                    "message": "Activated users are not subject to usage limits"
                }

            total_count = api_usage_repo.get_endpoints_total_usage_count(user_id, endpoints, days)

            # Calculate remaining calls
            remaining = max(0, limit - total_count)

            # Prepare limit information
            limit_info = {
                "is_allowed": True,  # Always True since this is just for querying
                "is_activated": False,
                "total_usage": total_count,
                "limit": limit,
                "remaining": remaining,
                "period_days": days,
                "endpoint_counts": {}
            }

            return limit_info

        except Exception as e:
            logger.error(f"Error getting monthly limit info: {str(e)}")
            # In case of error, return error information
            return {
                "is_allowed": True,
                "error": str(e),
                "limit": limit,
                "period_days": days
            }

# Create a singleton instance
usage_limiter = UsageLimiter()
