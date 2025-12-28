"""
API Usage Statistics

This module provides functions for retrieving API usage statistics.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from sqlalchemy import func, and_, or_, desc, asc

from src.models.db import ApiUsage
from src.utils.db_utils import get_db_session
from src.utils.api_usage_repository import api_usage_repo

# 配置日志
logger = logging.getLogger('api_usage_stats')

def get_user_usage_summary(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get a summary of API usage for a specific user.
    
    Args:
        user_id: ID of the user
        days: Number of days to look back
        
    Returns:
        Dictionary containing usage summary
    """
    try:
        # Get total usage count
        total_count = api_usage_repo.get_user_usage_count(user_id, days)
        
        # Get usage by endpoint
        endpoint_counts = api_usage_repo.get_user_usage_by_endpoint(user_id, days)
        
        # Get recent calls
        def _get_field(obj, key):
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        recent_calls = api_usage_repo.get_recent_user_calls(user_id, 10)
        recent_calls_data = []
        for call in recent_calls:
            recent_calls_data.append({
                "endpoint": _get_field(call, "endpoint"),
                "query": _get_field(call, "query"),
                "status": _get_field(call, "status"),
                "created_at": _get_field(call, "created_at"),
                "execution_time": _get_field(call, "execution_time"),
            })
        
        # Calculate daily usage
        daily_usage = get_daily_usage(user_id, days)
        
        return {
            "user_id": user_id,
            "period_days": days,
            "total_calls": total_count,
            "endpoint_breakdown": endpoint_counts,
            "recent_calls": recent_calls_data,
            "daily_usage": daily_usage
        }
    except Exception as e:
        logger.error(f"Error getting user usage summary: {e}")
        return {
            "error": str(e),
            "total_calls": 0,
            "endpoint_breakdown": {},
            "recent_calls": [],
            "daily_usage": []
        }

def get_daily_usage(user_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Get daily API usage for a specific user.
    
    Args:
        user_id: ID of the user
        days: Number of days to look back
        
    Returns:
        List of dictionaries containing daily usage data
    """
    try:
        with get_db_session() as session:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
            
            # Query to get daily counts
            query = session.query(
                func.date(ApiUsage.created_at).label('date'),
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.user_id == user_id,
                ApiUsage.created_at >= start_date
            ).group_by(
                func.date(ApiUsage.created_at)
            ).order_by(
                asc('date')
            )
            
            results = query.all()
            
            # Convert to list of dictionaries
            daily_data = []
            for row in results:
                row_date = row.date
                if isinstance(row_date, (datetime, date)):
                    date_str = row_date.strftime("%Y-%m-%d")
                elif isinstance(row_date, str):
                    date_str = row_date
                else:
                    date_str = None
                daily_data.append({
                    "date": date_str,
                    "count": row.count
                })
            
            # Fill in missing days with zero counts
            date_dict = {item["date"]: item["count"] for item in daily_data}
            complete_data = []
            
            current_date = start_date
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                complete_data.append({
                    "date": date_str,
                    "count": date_dict.get(date_str, 0)
                })
                current_date += timedelta(days=1)
            
            return complete_data
    except Exception as e:
        logger.error(f"Error getting daily usage: {e}")
        return []

def get_top_users(days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the top users by API usage.
    
    Args:
        days: Number of days to look back
        limit: Maximum number of users to return
        
    Returns:
        List of dictionaries containing user usage data
    """
    try:
        with get_db_session() as session:
            start_date = datetime.now() - timedelta(days=days)
            
            # Query to get user counts
            query = session.query(
                ApiUsage.user_id,
                func.count(ApiUsage.id).label('count')
            ).filter(
                ApiUsage.created_at >= start_date
            ).group_by(
                ApiUsage.user_id
            ).order_by(
                desc('count')
            ).limit(limit)
            
            results = query.all()
            
            # Convert to list of dictionaries
            user_data = []
            for row in results:
                user_data.append({
                    "user_id": row.user_id,
                    "call_count": row.count
                })
            
            return user_data
    except Exception as e:
        logger.error(f"Error getting top users: {e}")
        return []

def get_endpoint_stats(days: int = 30) -> Dict[str, Any]:
    """
    Get statistics for each API endpoint.
    
    Args:
        days: Number of days to look back
        
    Returns:
        Dictionary containing endpoint statistics
    """
    try:
        with get_db_session() as session:
            start_date = datetime.now() - timedelta(days=days)
            
            # Query to get endpoint counts
            query = session.query(
                ApiUsage.endpoint,
                func.count(ApiUsage.id).label('count'),
                func.avg(ApiUsage.execution_time).label('avg_time'),
                func.min(ApiUsage.execution_time).label('min_time'),
                func.max(ApiUsage.execution_time).label('max_time')
            ).filter(
                ApiUsage.created_at >= start_date
            ).group_by(
                ApiUsage.endpoint
            ).order_by(
                desc('count')
            )
            
            results = query.all()
            
            # Convert to dictionary
            endpoint_data = {}
            for row in results:
                endpoint_data[row.endpoint] = {
                    "count": row.count,
                    "avg_execution_time": row.avg_time,
                    "min_execution_time": row.min_time,
                    "max_execution_time": row.max_time
                }
            
            return endpoint_data
    except Exception as e:
        logger.error(f"Error getting endpoint stats: {e}")
        return {}
