"""
API Usage Tracker

This module provides functions for tracking API usage.
"""

import logging
from typing import Optional
from flask import request

# Import user utilities
from server.utils.user_utils import get_current_user_id

# Set up logger
logger = logging.getLogger('server.utils.api_usage_tracker')

_api_usage_repo = None
_api_usage_repo_load_failed = False


def _get_api_usage_repo():
    global _api_usage_repo
    global _api_usage_repo_load_failed

    if _api_usage_repo is not None:
        return _api_usage_repo
    if _api_usage_repo_load_failed:
        return None

    try:
        from src.utils.api_usage_repository import api_usage_repo  # type: ignore

        _api_usage_repo = api_usage_repo
        return _api_usage_repo
    except Exception as exc:  # noqa: BLE001
        _api_usage_repo_load_failed = True
        logger.warning("API usage repo unavailable; skipping tracking: %s", exc)
        return None

def track_api_call(endpoint: str,
                  query: Optional[str] = None,
                  query_type: Optional[str] = None,
                  scholar_id: Optional[str] = None,
                  status: str = "success",
                  error_message: Optional[str] = None,
                  execution_time: Optional[float] = None,
                  user_id: Optional[str] = None) -> None:
    """
    Track an API call in the database.

    Args:
        endpoint: API endpoint that was called
        query: The query parameter used in the API call
        query_type: Type of query (e.g., 'scholar_name', 'scholar_id')
        scholar_id: Scholar ID if available
        status: Status of the API call (success, error)
        error_message: Error message if the call failed
        execution_time: Execution time in seconds
        user_id: User ID who made the API call (optional, will try to get from Flask context if not provided)
    """
    try:
        api_usage_repo = _get_api_usage_repo()
        if api_usage_repo is None:
            return

        # Check if we're in a Flask application context
        from flask import has_app_context, has_request_context

        # 如果没有传入用户ID，尝试从Flask上下文获取
        if user_id is None:
            if has_app_context() and has_request_context():
                # 从Flask的g对象获取用户ID
                user_id = get_current_user_id()
            else:
                # 如果无法获取用户ID，设为匿名
                user_id = 'anonymous'
                logger.warning(f"无法获取用户ID，API调用将被记录为匿名: {endpoint}")

        # 获取客户端信息
        if has_app_context() and has_request_context():
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')
        else:
            # 在Flask上下文之外，使用默认值
            ip_address = '0.0.0.0'
            user_agent = 'API Call Outside Context'
            logger.info(f"在Flask上下文之外追踪API调用: {endpoint}, 用户ID: {user_id}")

        # Log the API call
        api_usage = api_usage_repo.log_api_call(
            user_id=user_id,
            endpoint=endpoint,
            query=query,
            query_type=query_type,
            scholar_id=scholar_id,
            status=status,
            error_message=error_message,
            execution_time=execution_time,
            ip_address=ip_address,
            user_agent=user_agent
        )

        if api_usage:
            logger.info(f"API call tracked: {endpoint} by user {user_id}")
        else:
            logger.warning(f"Failed to track API call: {endpoint} by user {user_id}")
    except Exception as e:
        logger.error(f"Error tracking API call: {str(e)}")

def check_rate_limit(user_id: str, endpoint: str, limit: int = 100, period_hours: int = 24) -> bool:
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
        api_usage_repo = _get_api_usage_repo()
        if api_usage_repo is None:
            return True
        return api_usage_repo.check_user_rate_limit(user_id, endpoint, limit, period_hours)
    except Exception as e:
        logger.error(f"Error checking rate limit: {str(e)}")
        # In case of error, allow the request to proceed
        return True

def track_stream_completion(endpoint: str, query: str, scholar_id: Optional[str] = None, status: str = "success", error_message: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """
    Track the completion of a streaming API call.
    This function should be called when a streaming response is completed.

    Args:
        endpoint: API endpoint that was called
        query: The query parameter used in the API call
        scholar_id: Scholar ID if available
        status: Status of the API call (success, error)
        error_message: Error message if the call failed
        user_id: User ID who made the API call (optional, will try to get from Flask context if not provided)
    """
    try:
        # Determine query type
        query_type = "scholar_id" if scholar_id else "scholar_name"

        # Track the API call
        track_api_call(
            endpoint=endpoint,
            query=query,
            query_type=query_type,
            scholar_id=scholar_id,
            status=status,
            error_message=error_message,
            user_id=user_id
        )
    except Exception as e:
        logger.error(f"Error tracking stream completion: {str(e)}")
