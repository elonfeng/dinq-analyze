"""
LinkedIn Repository Service

This module provides database operations for LinkedIn profile data.
It handles CRUD operations for LinkedIn profiles in the database.
"""

import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from src.models.db import LinkedInProfile
from src.utils.db_utils import get_db_session

logger = logging.getLogger(__name__)

class LinkedInRepository:
    """LinkedIn profile repository for database operations"""
    
    def create(self, data: Dict[str, Any]) -> Optional[LinkedInProfile]:
        """
        Create a new LinkedIn profile record.
        
        Args:
            data: LinkedIn profile data
            
        Returns:
            Created LinkedInProfile object or None
        """
        try:
            with get_db_session() as session:
                linkedin_profile = LinkedInProfile(**data)
                session.add(linkedin_profile)
                session.commit()
                session.refresh(linkedin_profile)
                
                logger.info(f"Created LinkedIn profile record for: {data.get('person_name', 'Unknown')}")
                return linkedin_profile
                
        except Exception as e:
            logger.error(f"Error creating LinkedIn profile record: {e}")
            return None
    
    def get_by_id(self, record_id: int) -> Optional[LinkedInProfile]:
        """
        Get LinkedIn profile by record ID.
        
        Args:
            record_id: Database record ID
            
        Returns:
            LinkedInProfile object or None
        """
        try:
            with get_db_session() as session:
                linkedin_profile = session.query(LinkedInProfile).filter(
                    LinkedInProfile.id == record_id
                ).first()
                
                return linkedin_profile
                
        except Exception as e:
            logger.error(f"Error getting LinkedIn profile by ID {record_id}: {e}")
            return None
    
    def get_by_linkedin_id(self, linkedin_id: str) -> Optional[LinkedInProfile]:
        """
        Get LinkedIn profile by LinkedIn ID.
        
        Args:
            linkedin_id: LinkedIn profile ID
            
        Returns:
            LinkedInProfile object or None
        """
        try:
            with get_db_session() as session:
                linkedin_profile = session.query(LinkedInProfile).filter(
                    LinkedInProfile.linkedin_id == linkedin_id
                ).first()
                
                return linkedin_profile
                
        except Exception as e:
            logger.error(f"Error getting LinkedIn profile by LinkedIn ID {linkedin_id}: {e}")
            return None
    
    def get_by_person_name(self, person_name: str) -> List[LinkedInProfile]:
        """
        Get LinkedIn profiles by person name.
        
        Args:
            person_name: Person's name
            
        Returns:
            List of LinkedInProfile objects
        """
        try:
            with get_db_session() as session:
                linkedin_profiles = session.query(LinkedInProfile).filter(
                    LinkedInProfile.person_name == person_name
                ).all()
                
                return linkedin_profiles
                
        except Exception as e:
            logger.error(f"Error getting LinkedIn profiles by person name {person_name}: {e}")
            return []
    
    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """
        Update LinkedIn profile record.
        
        Args:
            record_id: Database record ID
            data: Data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as session:
                linkedin_profile = session.query(LinkedInProfile).filter(
                    LinkedInProfile.id == record_id
                ).first()
                
                if not linkedin_profile:
                    logger.warning(f"LinkedIn profile record not found for ID: {record_id}")
                    return False
                
                # Update fields
                for key, value in data.items():
                    if hasattr(linkedin_profile, key):
                        setattr(linkedin_profile, key, value)
                
                linkedin_profile.last_updated = datetime.now()
                session.commit()
                
                logger.info(f"Updated LinkedIn profile record for ID: {record_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating LinkedIn profile record {record_id}: {e}")
            return False
    
    def update_by_linkedin_id(self, linkedin_id: str, data: Dict[str, Any]) -> bool:
        """
        Update LinkedIn profile record by LinkedIn ID.
        
        Args:
            linkedin_id: LinkedIn profile ID
            data: Data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as session:
                linkedin_profile = session.query(LinkedInProfile).filter(
                    LinkedInProfile.linkedin_id == linkedin_id
                ).first()
                
                if not linkedin_profile:
                    logger.warning(f"LinkedIn profile record not found for LinkedIn ID: {linkedin_id}")
                    return False
                
                # Update fields
                for key, value in data.items():
                    if hasattr(linkedin_profile, key):
                        setattr(linkedin_profile, key, value)
                
                linkedin_profile.last_updated = datetime.now()
                session.commit()
                
                logger.info(f"Updated LinkedIn profile record for LinkedIn ID: {linkedin_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating LinkedIn profile record {linkedin_id}: {e}")
            return False
    
    def delete(self, record_id: int) -> bool:
        """
        Delete LinkedIn profile record.
        
        Args:
            record_id: Database record ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as session:
                linkedin_profile = session.query(LinkedInProfile).filter(
                    LinkedInProfile.id == record_id
                ).first()
                
                if not linkedin_profile:
                    logger.warning(f"LinkedIn profile record not found for ID: {record_id}")
                    return False
                
                session.delete(linkedin_profile)
                session.commit()
                
                logger.info(f"Deleted LinkedIn profile record for ID: {record_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting LinkedIn profile record {record_id}: {e}")
            return False
    
    def delete_by_linkedin_id(self, linkedin_id: str) -> bool:
        """
        Delete LinkedIn profile record by LinkedIn ID.
        
        Args:
            linkedin_id: LinkedIn profile ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as session:
                linkedin_profile = session.query(LinkedInProfile).filter(
                    LinkedInProfile.linkedin_id == linkedin_id
                ).first()
                
                if not linkedin_profile:
                    logger.warning(f"LinkedIn profile record not found for LinkedIn ID: {linkedin_id}")
                    return False
                
                session.delete(linkedin_profile)
                session.commit()
                
                logger.info(f"Deleted LinkedIn profile record for LinkedIn ID: {linkedin_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting LinkedIn profile record {linkedin_id}: {e}")
            return False
    
    def get_all(self, limit: int = None, offset: int = 0) -> List[LinkedInProfile]:
        """
        Get all LinkedIn profile records.
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of LinkedInProfile objects
        """
        try:
            with get_db_session() as session:
                query = session.query(LinkedInProfile).order_by(LinkedInProfile.created_at.desc())
                
                if offset > 0:
                    query = query.offset(offset)
                
                if limit:
                    query = query.limit(limit)
                
                linkedin_profiles = query.all()
                return linkedin_profiles
                
        except Exception as e:
            logger.error(f"Error getting all LinkedIn profile records: {e}")
            return []
    
    def count(self) -> int:
        """
        Get total count of LinkedIn profile records.
        
        Returns:
            Total count
        """
        try:
            with get_db_session() as session:
                count = session.query(LinkedInProfile).count()
                return count
                
        except Exception as e:
            logger.error(f"Error counting LinkedIn profile records: {e}")
            return 0
    
    def get_recent(self, days: int = 7) -> List[LinkedInProfile]:
        """
        Get recent LinkedIn profile records.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of LinkedInProfile objects
        """
        try:
            with get_db_session() as session:
                cutoff_date = datetime.now() - timedelta(days=days)
                linkedin_profiles = session.query(LinkedInProfile).filter(
                    LinkedInProfile.created_at >= cutoff_date
                ).order_by(LinkedInProfile.created_at.desc()).all()
                
                return linkedin_profiles
                
        except Exception as e:
            logger.error(f"Error getting recent LinkedIn profile records: {e}")
            return []

# Create global repository instance
linkedin_repo = LinkedInRepository()

# For compatibility, provide function interface
def get_linkedin_by_id(linkedin_id: str) -> Optional[Dict[str, Any]]:
    """Get LinkedIn profile by LinkedIn ID"""
    try:
        with get_db_session() as session:
            linkedin_profile = session.query(LinkedInProfile).filter(
                LinkedInProfile.linkedin_id == linkedin_id
            ).first()
            if linkedin_profile:
                return {
                    'linkedin_id': linkedin_profile.linkedin_id,
                    'person_name': linkedin_profile.person_name,
                    'linkedin_url': linkedin_profile.linkedin_url,
                    'profile_data': linkedin_profile.profile_data,
                    'last_updated': linkedin_profile.last_updated.isoformat() if linkedin_profile.last_updated else None,
                    'created_at': linkedin_profile.created_at.isoformat() if linkedin_profile.created_at else None
                }
    except Exception as e:
        logger.error(f"Error getting LinkedIn profile by ID: {e}")
    return None 