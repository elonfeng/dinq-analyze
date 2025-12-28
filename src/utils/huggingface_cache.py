"""
HuggingFace Cache Service

This module provides caching functionality for HuggingFace profile analysis results.
It helps reduce API calls and improve response times for repeated queries.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.models.db import HuggingFaceProfile
from src.utils.db_utils import get_db_session

logger = logging.getLogger(__name__)

def get_huggingface_from_cache(username: str, max_age_days: int = 30, user_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Get HuggingFace profile data from cache.
    
    Args:
        username: HuggingFace username
        max_age_days: Maximum age of cached data in days
        user_id: User ID for logging purposes
        
    Returns:
        Cached HuggingFace data or None if not found or too old
    """
    try:
        with get_db_session() as session:
            # Query for the HuggingFace profile
            hf_profile = session.query(HuggingFaceProfile).filter(
                HuggingFaceProfile.username == username
            ).first()
            
            if not hf_profile:
                logger.debug(f"No cached data found for HuggingFace username: {username}")
                return None
            
            # Check if data is recent enough
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            if hf_profile.last_updated < cutoff_date:
                logger.debug(f"Cached data for HuggingFace username {username} is too old (last updated: {hf_profile.last_updated})")
                return None
            
            logger.info(f"Found recent cached data for HuggingFace username: {username}")
            
            # Return the cached profile data
            cached_data = hf_profile.profile
                
            return cached_data
            
    except Exception as e:
        logger.error(f"Error retrieving HuggingFace data from cache for {username}: {e}")
        return None

def cache_huggingface_data(username: str, profile_data: Dict[str, Any], user_id: str = None) -> bool:
    """
    Cache HuggingFace profile data.
    
    Args:
        username: HuggingFace username
        profile_data: HuggingFace profile data to cache
        user_id: User ID who requested this analysis
        
    Returns:
        True if successfully cached, False otherwise
    """
    try:
        with get_db_session() as session:
            if not username:
                logger.error("Missing username for caching HuggingFace data")
                return False
            
            # Check if record already exists
            existing_profile = session.query(HuggingFaceProfile).filter(
                HuggingFaceProfile.username == username
            ).first()
            
            if existing_profile:
                # Update existing record
                existing_profile.profile = profile_data
                existing_profile.user_id = user_id or existing_profile.user_id
                existing_profile.last_updated = datetime.now()
                
                logger.info(f"Updated cached data for HuggingFace username: {username}")
            else:
                # Create new record
                new_profile = HuggingFaceProfile(
                    username=username,
                    profile=profile_data,
                    user_id=user_id
                )
                
                session.add(new_profile)
                logger.info(f"Cached new data for HuggingFace username: {username}")
            
            session.commit()
            return True
            
    except Exception as e:
        logger.error(f"Error caching HuggingFace data for {username}: {e}")
        return False

def update_huggingface_cache_partial(username: str, updates: Dict[str, Any]) -> bool:
    """
    Update specific fields in cached HuggingFace data.
    
    Args:
        username: HuggingFace username
        updates: Dictionary of fields to update
        
    Returns:
        True if successfully updated, False otherwise
    """
    try:
        with get_db_session() as session:
            hf_profile = session.query(HuggingFaceProfile).filter(
                HuggingFaceProfile.username == username
            ).first()
            
            if not hf_profile:
                logger.warning(f"No cached data found for HuggingFace username: {username}")
                return False
            
            # Update the profile data
            if hf_profile.profile:
                hf_profile.profile.update(updates)
            else:
                hf_profile.profile = updates
            
            hf_profile.last_updated = datetime.now()
            session.commit()
            
            logger.info(f"Updated cached data for HuggingFace username: {username}")
            return True
            
    except Exception as e:
        logger.error(f"Error updating cached HuggingFace data for {username}: {e}")
        return False

def clear_huggingface_cache(username: str = None) -> bool:
    """
    Clear HuggingFace cache data.
    
    Args:
        username: Specific username to clear, or None to clear all
        
    Returns:
        True if successfully cleared, False otherwise
    """
    try:
        with get_db_session() as session:
            if username:
                # Clear specific username
                deleted_count = session.query(HuggingFaceProfile).filter(
                    HuggingFaceProfile.username == username
                ).delete()
                
                logger.info(f"Cleared cache for HuggingFace username: {username}")
            else:
                # Clear all cache
                deleted_count = session.query(HuggingFaceProfile).delete()
                logger.info(f"Cleared all HuggingFace cache ({deleted_count} records)")
            
            session.commit()
            return True
            
    except Exception as e:
        logger.error(f"Error clearing HuggingFace cache: {e}")
        return False

def get_huggingface_cache_stats() -> Dict[str, Any]:
    """
    Get HuggingFace cache statistics.
    
    Returns:
        Dictionary with cache statistics
    """
    try:
        with get_db_session() as session:
            total_records = session.query(HuggingFaceProfile).count()
            
            # Recent records (last 24 hours)
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_records = session.query(HuggingFaceProfile).filter(
                HuggingFaceProfile.last_updated >= recent_cutoff
            ).count()
            
            # Recent records (last 7 days)
            week_cutoff = datetime.now() - timedelta(days=7)
            week_records = session.query(HuggingFaceProfile).filter(
                HuggingFaceProfile.last_updated >= week_cutoff
            ).count()
            
            return {
                'total_records': total_records,
                'recent_records_24h': recent_records,
                'recent_records_7d': week_records,
                'cache_hit_rate': 'N/A'  # Could be calculated with additional tracking
            }
            
    except Exception as e:
        logger.error(f"Error getting HuggingFace cache stats: {e}")
        return {
            'total_records': 0,
            'recent_records_24h': 0,
            'recent_records_7d': 0,
            'cache_hit_rate': 'Error'
        }

def cleanup_old_huggingface_cache(max_age_days: int = 30) -> int:
    """
    Clean up old HuggingFace cache entries.
    
    Args:
        max_age_days: Maximum age of cache entries to keep
        
    Returns:
        Number of records deleted
    """
    try:
        with get_db_session() as session:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            deleted_count = session.query(HuggingFaceProfile).filter(
                HuggingFaceProfile.last_updated < cutoff_date
            ).delete()
            
            session.commit()
            
            logger.info(f"Cleaned up {deleted_count} old HuggingFace cache entries (older than {max_age_days} days)")
            return deleted_count
            
    except Exception as e:
        logger.error(f"Error cleaning up old HuggingFace cache: {e}")
        return 0
