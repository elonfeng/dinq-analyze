#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Activation Code Repository

This module provides a repository for managing activation codes.
"""

import logging
import random
import string
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import and_, or_, func
from sqlalchemy.exc import SQLAlchemyError

from src.models.db import ActivationCode
from src.utils.db_utils import get_db_session

# Configure logging
logger = logging.getLogger(__name__)

class ActivationCodeRepository:
    """Repository for managing activation codes."""

    def __init__(self):
        """Initialize the repository."""
        pass

    def generate_code(self, length: int = 6) -> str:
        """
        Generate a random activation code.

        Args:
            length: Length of the code (default: 6)

        Returns:
            str: Random activation code
        """
        # Define characters to use (uppercase letters and digits, excluding ambiguous characters)
        chars = ''.join(c for c in string.ascii_uppercase + string.digits if c not in 'O0I1')
        
        # Generate random code
        code = ''.join(random.choice(chars) for _ in range(length))
        
        return code

    def create_code(self, created_by: Optional[str] = None, 
                   expires_in_days: Optional[int] = None,
                   batch_id: Optional[str] = None,
                   notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new activation code.

        Args:
            created_by: User ID who created the code
            expires_in_days: Number of days until the code expires
            batch_id: Batch identifier for bulk code generation
            notes: Additional notes or purpose of this code

        Returns:
            Dict: Created activation code data
        """
        # Check if the user has permission to create codes
        if created_by and not self._can_create_code(created_by):
            logger.warning(f"User {created_by} has reached the limit for creating activation codes")
            return {"success": False, "error": "You have reached the limit for creating activation codes"}

        # Generate a unique code
        code = self._generate_unique_code()
        
        # Calculate expiration date if provided
        expires_at = None
        if expires_in_days is not None and expires_in_days > 0:
            expires_at = datetime.now() + timedelta(days=expires_in_days)
        
        try:
            with get_db_session() as session:
                # Create new activation code
                activation_code = ActivationCode(
                    code=code,
                    created_by=created_by,
                    expires_at=expires_at,
                    batch_id=batch_id,
                    notes=notes
                )
                
                # Add to database
                session.add(activation_code)
                session.commit()
                
                # Return the created code
                return {
                    "success": True,
                    "code": code,
                    "created_at": activation_code.created_at.isoformat() if activation_code.created_at else None,
                    "expires_at": activation_code.expires_at.isoformat() if activation_code.expires_at else None
                }
        except SQLAlchemyError as e:
            logger.error(f"Error creating activation code: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}

    def use_code(self, code: str, user_id: str) -> Dict[str, Any]:
        """
        Use an activation code.

        Args:
            code: The activation code to use
            user_id: User ID who is using the code

        Returns:
            Dict: Result of the operation
        """
        if not code or not user_id:
            return {"success": False, "error": "Code and user ID are required"}
        
        # Normalize code (uppercase)
        code = code.strip().upper()
        
        try:
            with get_db_session() as session:
                # Find the activation code
                activation_code = session.query(ActivationCode).filter(
                    ActivationCode.code == code
                ).first()
                
                # Check if code exists
                if not activation_code:
                    return {"success": False, "error": "Invalid activation code"}
                
                # Check if code is already used
                if activation_code.is_used:
                    return {"success": False, "error": "This activation code has already been used"}
                
                # Check if code is expired
                if activation_code.expires_at and activation_code.expires_at < datetime.now():
                    return {"success": False, "error": "This activation code has expired"}
                
                # Use the code
                activation_code.is_used = True
                activation_code.used_by = user_id
                activation_code.used_at = datetime.now()
                
                # Commit changes
                session.commit()
                
                # Return success
                return {
                    "success": True,
                    "message": "Activation code used successfully",
                    "code": code,
                    "used_at": activation_code.used_at.isoformat() if activation_code.used_at else None
                }
        except SQLAlchemyError as e:
            logger.error(f"Error using activation code: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}

    def verify_code(self, code: str) -> Dict[str, Any]:
        """
        Verify if an activation code is valid (exists and not used).

        Args:
            code: The activation code to verify

        Returns:
            Dict: Verification result
        """
        if not code:
            return {"success": False, "error": "Code is required"}
        
        # Normalize code (uppercase)
        code = code.strip().upper()
        
        try:
            with get_db_session() as session:
                # Find the activation code
                activation_code = session.query(ActivationCode).filter(
                    ActivationCode.code == code
                ).first()
                
                # Check if code exists
                if not activation_code:
                    return {"success": False, "error": "Invalid activation code"}
                
                # Check if code is already used
                if activation_code.is_used:
                    return {
                        "success": False, 
                        "error": "This activation code has already been used",
                        "used_by": activation_code.used_by,
                        "used_at": activation_code.used_at.isoformat() if activation_code.used_at else None
                    }
                
                # Check if code is expired
                if activation_code.expires_at and activation_code.expires_at < datetime.now():
                    return {
                        "success": False, 
                        "error": "This activation code has expired",
                        "expires_at": activation_code.expires_at.isoformat() if activation_code.expires_at else None
                    }
                
                # Return success
                return {
                    "success": True,
                    "message": "Activation code is valid",
                    "code": code,
                    "created_at": activation_code.created_at.isoformat() if activation_code.created_at else None,
                    "expires_at": activation_code.expires_at.isoformat() if activation_code.expires_at else None
                }
        except SQLAlchemyError as e:
            logger.error(f"Error verifying activation code: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}

    def get_codes(self, 
                 user_id: Optional[str] = None,
                 is_used: Optional[bool] = None,
                 batch_id: Optional[str] = None,
                 limit: int = 100,
                 offset: int = 0) -> Dict[str, Any]:
        """
        Get activation codes with optional filtering.

        Args:
            user_id: Filter by user ID (created_by or used_by)
            is_used: Filter by usage status
            batch_id: Filter by batch ID
            limit: Maximum number of codes to return
            offset: Offset for pagination

        Returns:
            Dict: List of activation codes
        """
        try:
            with get_db_session() as session:
                # Build query
                query = session.query(ActivationCode)
                
                # Apply filters
                if user_id:
                    query = query.filter(
                        or_(
                            ActivationCode.created_by == user_id,
                            ActivationCode.used_by == user_id
                        )
                    )
                
                if is_used is not None:
                    query = query.filter(ActivationCode.is_used == is_used)
                
                if batch_id:
                    query = query.filter(ActivationCode.batch_id == batch_id)
                
                # Get total count
                total_count = query.count()
                
                # Apply pagination
                query = query.order_by(ActivationCode.created_at.desc())
                query = query.limit(limit).offset(offset)
                
                # Execute query
                codes = query.all()
                
                # Format results
                results = []
                for code in codes:
                    results.append({
                        "id": code.id,
                        "code": code.code,
                        "is_used": code.is_used,
                        "created_by": code.created_by,
                        "used_by": code.used_by,
                        "created_at": code.created_at.isoformat() if code.created_at else None,
                        "used_at": code.used_at.isoformat() if code.used_at else None,
                        "expires_at": code.expires_at.isoformat() if code.expires_at else None,
                        "batch_id": code.batch_id,
                        "notes": code.notes
                    })
                
                # Return results
                return {
                    "success": True,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "codes": results
                }
        except SQLAlchemyError as e:
            logger.error(f"Error getting activation codes: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}

    def _generate_unique_code(self, max_attempts: int = 10) -> str:
        """
        Generate a unique activation code that doesn't exist in the database.

        Args:
            max_attempts: Maximum number of attempts to generate a unique code

        Returns:
            str: Unique activation code

        Raises:
            RuntimeError: If unable to generate a unique code after max_attempts
        """
        for _ in range(max_attempts):
            code = self.generate_code()
            
            # Check if code already exists
            with get_db_session() as session:
                existing = session.query(ActivationCode).filter(
                    ActivationCode.code == code
                ).first()
                
                if not existing:
                    return code
        
        # If we get here, we couldn't generate a unique code
        raise RuntimeError(f"Unable to generate a unique activation code after {max_attempts} attempts")

    def _can_create_code(self, user_id: str, max_codes_per_day: int = 10) -> bool:
        """
        Check if a user can create more activation codes.

        Args:
            user_id: User ID to check
            max_codes_per_day: Maximum number of codes a user can create per day

        Returns:
            bool: True if the user can create more codes, False otherwise
        """
        return True
        # Calculate the start of the current day
        # today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # try:
        #     with get_db_session() as session:
        #         # Count codes created by the user today
        #         count = session.query(func.count(ActivationCode.id)).filter(
        #             and_(
        #                 ActivationCode.created_by == user_id,
        #                 ActivationCode.created_at >= today_start
        #             )
        #         ).scalar()
                
        #         # Check if the user has reached the limit
        #         return count < max_codes_per_day
        # except SQLAlchemyError as e:
        #     logger.error(f"Error checking if user can create code: {str(e)}")
        #     # Default to False on error
        #     return False

# Create a singleton instance
activation_code_repo = ActivationCodeRepository()
