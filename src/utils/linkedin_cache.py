"""
LinkedIn Cache Service

This module provides caching functionality for LinkedIn profile analysis results.
It helps reduce API calls and improve response times for repeated queries.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.models.db import LinkedInProfile
from src.utils.db_utils import get_db_session

logger = logging.getLogger(__name__)

def get_linkedin_from_cache(linkedin_id: str, max_age_days: int = 7, person_name: str = None) -> Optional[Dict[str, Any]]:
    """
    Get LinkedIn profile data from cache if it exists and is recent enough.
    
    Args:
        linkedin_id: LinkedIn profile ID
        max_age_days: Maximum age of cached data in days
        person_name: Person's name for additional validation
        
    Returns:
        Cached LinkedIn data or None if not found or too old
    """
    try:
        with get_db_session() as session:
            # Query for the LinkedIn profile
            linkedin_profile = session.query(LinkedInProfile).filter(
                LinkedInProfile.linkedin_id == linkedin_id
            ).first()
            
            if not linkedin_profile:
                logger.debug(f"No cached data found for LinkedIn ID: {linkedin_id}")
                return None
            
            # Check if data is recent enough
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            if linkedin_profile.last_updated < cutoff_date:
                logger.debug(f"Cached data for LinkedIn ID {linkedin_id} is too old (last updated: {linkedin_profile.last_updated})")
                return None

            
            # Convert to dictionary format
            cached_data = {
                'linkedin_id': linkedin_profile.linkedin_id,
                'person_name': linkedin_profile.person_name,
                'linkedin_url': linkedin_profile.linkedin_url,
                'profile_data': linkedin_profile.profile_data,
                'last_updated': linkedin_profile.last_updated.isoformat() if linkedin_profile.last_updated else None,
                'created_at': linkedin_profile.created_at.isoformat() if linkedin_profile.created_at else None
            }
            
            logger.info(f"Retrieved cached data for LinkedIn ID: {linkedin_id}")
            return cached_data
            
    except Exception as e:
        logger.error(f"Error retrieving LinkedIn data from cache: {e}")
        return None

def cache_linkedin_data(linkedin_data: Dict[str, Any]) -> bool:
    """
    Cache LinkedIn profile data.
    
    Args:
        linkedin_data: LinkedIn profile data to cache
        
    Returns:
        True if successfully cached, False otherwise
    """
    try:
        with get_db_session() as session:
            linkedin_id = linkedin_data.get('linkedin_id')
            person_name = linkedin_data.get('person_name')
            
            if not linkedin_id or not person_name:
                logger.error("Missing required fields for caching LinkedIn data")
                return False
            
            # Check if record already exists
            existing_profile = session.query(LinkedInProfile).filter(
                LinkedInProfile.linkedin_id == linkedin_id
            ).first()
            
            if existing_profile:
                # Update existing record
                existing_profile.person_name = person_name
                existing_profile.linkedin_url = linkedin_data.get('linkedin_url')
                existing_profile.profile_data = linkedin_data.get('profile_data')
                existing_profile.last_updated = datetime.now()
                
                logger.info(f"Updated cached data for LinkedIn ID: {linkedin_id}")
            else:
                # Create new record
                new_profile = LinkedInProfile(
                    linkedin_id=linkedin_id,
                    person_name=person_name,
                    linkedin_url=linkedin_data.get('linkedin_url'),
                    profile_data=linkedin_data.get('profile_data')
                )
                
                session.add(new_profile)
                logger.info(f"Cached new data for LinkedIn ID: {linkedin_id}")
            
            session.commit()
            return True
            
    except Exception as e:
        logger.error(f"Error caching LinkedIn data: {e}")
        return False

def update_linkedin_cache_partial(linkedin_id: str, updates: Dict[str, Any]) -> bool:
    """
    Update specific fields in cached LinkedIn data.
    
    Args:
        linkedin_id: LinkedIn profile ID
        updates: Dictionary of fields to update (supports nested updates like {'profile_data': {...}})
        
    Returns:
        True if successfully updated, False otherwise
    """
    try:
        with get_db_session() as session:
            linkedin_profile = session.query(LinkedInProfile).filter(
                LinkedInProfile.linkedin_id == linkedin_id
            ).first()
            
            if not linkedin_profile:
                logger.warning(f"No cached data found for LinkedIn ID: {linkedin_id}")
                return False
            
            # Update specified fields
            for field, value in updates.items():
                if hasattr(linkedin_profile, field):
                    if field == 'profile_data' and isinstance(value, dict):
                        # Handle nested profile_data updates
                        current_profile_data = linkedin_profile.profile_data or {}
                        current_profile_data.update(value)
                        setattr(linkedin_profile, field, current_profile_data)
                    else:
                        setattr(linkedin_profile, field, value)
            
            linkedin_profile.last_updated = datetime.now()
            session.commit()
            
            logger.info(f"Updated partial cached data for LinkedIn ID: {linkedin_id}")
            return True
            
    except Exception as e:
        logger.error(f"Error updating LinkedIn cache: {e}")
        return False

def clear_linkedin_cache(linkedin_id: str = None) -> bool:
    """
    Clear LinkedIn cache data.
    
    Args:
        linkedin_id: Specific LinkedIn ID to clear, or None to clear all
        
    Returns:
        True if successfully cleared, False otherwise
    """
    try:
        with get_db_session() as session:
            if linkedin_id:
                # Clear specific record
                deleted_count = session.query(LinkedInProfile).filter(
                    LinkedInProfile.linkedin_id == linkedin_id
                ).delete()
                logger.info(f"Cleared cache for LinkedIn ID: {linkedin_id} ({deleted_count} records)")
            else:
                # Clear all records
                deleted_count = session.query(LinkedInProfile).delete()
                logger.info(f"Cleared all LinkedIn cache ({deleted_count} records)")
            
            session.commit()
            return True
            
    except Exception as e:
        logger.error(f"Error clearing LinkedIn cache: {e}")
        return False

def get_linkedin_cache_stats() -> Dict[str, Any]:
    """
    Get LinkedIn cache statistics.
    
    Returns:
        Dictionary containing cache statistics
    """
    try:
        with get_db_session() as session:
            total_records = session.query(LinkedInProfile).count()
            
            # Get records updated in last 24 hours
            yesterday = datetime.now() - timedelta(days=1)
            recent_records = session.query(LinkedInProfile).filter(
                LinkedInProfile.last_updated >= yesterday
            ).count()
            
            # Get oldest and newest records
            oldest_record = session.query(LinkedInProfile).order_by(LinkedInProfile.created_at.asc()).first()
            newest_record = session.query(LinkedInProfile).order_by(LinkedInProfile.created_at.desc()).first()
            
            stats = {
                'total_records': total_records,
                'recent_records_24h': recent_records,
                'oldest_record_date': oldest_record.created_at.isoformat() if oldest_record else None,
                'newest_record_date': newest_record.created_at.isoformat() if newest_record else None
            }
            
            return stats
            
    except Exception as e:
        logger.error(f"Error getting LinkedIn cache stats: {e}")
        return {} 