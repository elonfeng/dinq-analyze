"""
API Usage Repository

This module provides a repository for tracking API usage.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_, desc

from src.models.db import ApiUsage
from src.utils.db_utils import DatabaseRepository, get_db_session

# 配置日志
logger = logging.getLogger('api_usage_repository')

class ApiUsageRepository(DatabaseRepository[ApiUsage]):
    """Repository for API usage tracking"""

    def __init__(self):
        super().__init__(ApiUsage)

    def log_api_call(self,
                    user_id: str,
                    endpoint: str,
                    query: Optional[str] = None,
                    query_type: Optional[str] = None,
                    scholar_id: Optional[str] = None,
                    status: str = "success",
                    error_message: Optional[str] = None,
                    execution_time: Optional[float] = None,
                    ip_address: Optional[str] = None,
                    user_agent: Optional[str] = None) -> bool:
        """
        Log an API call to the database.

        Args:
            user_id: ID of the user making the API call
            endpoint: API endpoint that was called
            query: The query parameter used in the API call
            query_type: Type of query (e.g., 'scholar_name', 'scholar_id')
            scholar_id: Scholar ID if available
            status: Status of the API call (success, error)
            error_message: Error message if the call failed
            execution_time: Execution time in seconds
            ip_address: IP address of the client
            user_agent: User agent of the client

        Returns:
            True if the API call was successfully logged, False otherwise
        """
        try:
            api_usage_data = {
                "user_id": user_id,
                "endpoint": endpoint,
                "query": query,
                "query_type": query_type,
                "scholar_id": scholar_id,
                "status": status,
                "error_message": error_message,
                "execution_time": execution_time,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": datetime.now()
            }

            with get_db_session() as session:
                api_usage = ApiUsage(**api_usage_data)
                session.add(api_usage)
                session.flush()
                logger.info(f"API call logged: {endpoint} by user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error logging API call: {e}")
            return False

    def get_user_usage_count(self, user_id: str, days: int = 30) -> int:
        """
        Get the number of API calls made by a user in the last N days.

        Args:
            user_id: ID of the user
            days: Number of days to look back

        Returns:
            Number of API calls made by the user
        """
        try:
            with get_db_session() as session:
                start_date = datetime.now() - timedelta(days=days)
                count = session.query(func.count(ApiUsage.id))\
                    .filter(
                        ApiUsage.user_id == user_id,
                        ApiUsage.created_at >= start_date
                    ).scalar()
                return count
        except Exception as e:
            logger.error(f"Error getting user usage count: {e}")
            return 0

    def get_user_usage_by_endpoint(self, user_id: str, days: int = 30) -> Dict[str, int]:
        """
        Get the number of API calls made by a user per endpoint in the last N days.

        Args:
            user_id: ID of the user
            days: Number of days to look back

        Returns:
            Dictionary mapping endpoint names to call counts
        """
        try:
            with get_db_session() as session:
                start_date = datetime.now() - timedelta(days=days)
                results = session.query(
                    ApiUsage.endpoint,
                    func.count(ApiUsage.id).label('count')
                ).filter(
                    ApiUsage.user_id == user_id,
                    ApiUsage.created_at >= start_date
                ).group_by(ApiUsage.endpoint).all()

                return {row[0]: row[1] for row in results}
        except Exception as e:
            logger.error(f"Error getting user usage by endpoint: {e}")
            return {}

    def get_recent_user_calls(self, user_id: str, limit: int = 10) -> List[ApiUsage]:
        """
        Get the most recent API calls made by a user.

        Args:
            user_id: ID of the user
            limit: Maximum number of records to return

        Returns:
            List of ApiUsage records
        """
        try:
            with get_db_session() as session:
                calls = session.query(ApiUsage)\
                    .filter(ApiUsage.user_id == user_id)\
                    .order_by(desc(ApiUsage.created_at))\
                    .limit(limit)\
                    .all()
                return calls
        except Exception as e:
            logger.error(f"Error getting recent user calls: {e}")
            return []

    def get_endpoint_usage_count(self, user_id: str, endpoint: str, days: int = 30) -> int:
        """
        Get the number of API calls made by a user for a specific endpoint in the last N days.

        Args:
            user_id: ID of the user
            endpoint: API endpoint to check
            days: Number of days to look back

        Returns:
            Number of API calls made by the user for the specified endpoint
        """
        try:
            with get_db_session() as session:
                start_date = datetime.now() - timedelta(days=days)
                count = session.query(func.count(ApiUsage.id))\
                    .filter(
                        ApiUsage.user_id == user_id,
                        ApiUsage.endpoint == endpoint,
                        ApiUsage.created_at >= start_date
                    ).scalar()
                return count
        except Exception as e:
            logger.error(f"Error getting endpoint usage count: {e}")
            return 0

    def get_endpoints_total_usage_count(self, user_id: str, endpoints: List[str], days: int = 30) -> int:
        """
        Get the total number of API calls made by a user for multiple endpoints in the last N days.

        Args:
            user_id: ID of the user
            endpoints: List of API endpoints to check
            days: Number of days to look back

        Returns:
            Total number of API calls made by the user for the specified endpoints
        """
        try:
            with get_db_session() as session:
                start_date = datetime.now() - timedelta(days=days)
                count = session.query(func.count(ApiUsage.id))\
                    .filter(
                        ApiUsage.user_id == user_id,
                        ApiUsage.endpoint.in_(endpoints),
                        ApiUsage.created_at >= start_date
                    ).scalar()
                return count
        except Exception as e:
            logger.error(f"Error getting endpoints total usage count: {e}")
            return 0

    def check_user_rate_limit(self, user_id: str, endpoint: str, limit: int, period_hours: int = 24) -> bool:
        """
        Check if a user has exceeded their rate limit for a specific endpoint.

        Args:
            user_id: ID of the user
            endpoint: API endpoint to check
            limit: Maximum number of calls allowed in the period
            period_hours: Time period in hours

        Returns:
            True if the user has NOT exceeded their rate limit, False otherwise
        """
        try:
            with get_db_session() as session:
                start_date = datetime.now() - timedelta(hours=period_hours)
                count = session.query(func.count(ApiUsage.id))\
                    .filter(
                        ApiUsage.user_id == user_id,
                        ApiUsage.endpoint == endpoint,
                        ApiUsage.created_at >= start_date
                    ).scalar()

                return count < limit
        except Exception as e:
            logger.error(f"Error checking user rate limit: {e}")
            # In case of error, allow the request to proceed
            return True

# Create a singleton instance
api_usage_repo = ApiUsageRepository()
