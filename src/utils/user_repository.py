#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
User Repository

This module provides a repository for managing user information.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy import and_, or_, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.models.db import User, ActivationCode
from src.utils.db_utils import get_db_session

# Configure logging
logger = logging.getLogger(__name__)

class UserRepository:
    """Repository for managing user information."""

    def __init__(self):
        """Initialize the repository."""
        pass

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information by user ID.
        If the user doesn't exist, it will be created.

        Args:
            user_id: The user ID to get or create

        Returns:
            Dict: User information with activation status
        """
        if not user_id:
            return {"success": False, "error": "User ID is required"}

        try:
            with get_db_session() as session:
                # Try to find the user
                user = session.query(User).filter(User.user_id == user_id).first()
                
                # If user doesn't exist, create a new one
                if not user:
                    try:
                        logger.info(f"Creating new user with ID: {user_id}")
                        user = User(
                            user_id=user_id,
                            display_name=None,
                            is_activated=False
                        )
                        session.add(user)
                        session.commit()
                        session.refresh(user)
                    except IntegrityError:
                        session.rollback()
                        # 如果创建失败，重新查询用户
                        user = session.query(User).filter(User.user_id == user_id).first()
                
                # Get activation information
                activation_info = self._get_activation_info(session, user_id)
                
                # Update last login time
                user.last_login = datetime.now()
                session.commit()
                
                # Prepare response
                if not user:
                    return {"success": True,"user": {}}
                user_data = {
                    "user_id": user.user_id,
                    "display_name": user.display_name,
                    "email": user.email,
                    "profile_picture": user.profile_picture,
                    "is_activated": user.is_activated,
                    "activation_code": user.activation_code,
                    "activated_at": user.activated_at.isoformat() if user.activated_at else None,
                    "user_type": user.user_type,
                    "preferences": user.preferences,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
                
                # Add activation information
                user_data.update(activation_info)
                
                return {
                    "success": True,
                    "user": user_data
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Database error getting user {user_id}: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            return {"success": False, "error": f"Error: {str(e)}"}

    def update_user(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user information.

        Args:
            user_id: The user ID to update
            data: The data to update

        Returns:
            Dict: Updated user information
        """
        if not user_id:
            return {"success": False, "error": "User ID is required"}

        try:
            with get_db_session() as session:
                # Find the user
                user = session.query(User).filter(User.user_id == user_id).first()
                
                if not user:
                    return {"success": False, "error": "User not found"}
                
                # Update allowed fields
                allowed_fields = [
                    "display_name", "email", "profile_picture", "preferences"
                ]
                
                for field in allowed_fields:
                    if field in data and data[field] is not None:
                        setattr(user, field, data[field])
                
                # Save changes
                session.commit()
                
                # Get activation information
                activation_info = self._get_activation_info(session, user_id)
                
                # Prepare response
                user_data = {
                    "user_id": user.user_id,
                    "display_name": user.display_name,
                    "email": user.email,
                    "profile_picture": user.profile_picture,
                    "is_activated": user.is_activated,
                    "activation_code": user.activation_code,
                    "activated_at": user.activated_at.isoformat() if user.activated_at else None,
                    "user_type": user.user_type,
                    "preferences": user.preferences,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
                
                # Add activation information
                user_data.update(activation_info)
                
                return {
                    "success": True,
                    "user": user_data
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Database error updating user {user_id}: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            return {"success": False, "error": f"Error: {str(e)}"}

    def _get_activation_info(self, session, user_id: str) -> Dict[str, Any]:
        """
        Get activation information for a user.

        Args:
            session: Database session
            user_id: The user ID to get activation info for

        Returns:
            Dict: Activation information
        """
        # Check if the user has used an activation code
        activation_code = session.query(ActivationCode).filter(
            ActivationCode.used_by == user_id,
            ActivationCode.is_used == True
        ).first()
        
        if activation_code:
            return {
                "has_used_activation_code": True,
                "activation_code_details": {
                    "code": activation_code.code,
                    "used_at": activation_code.used_at.isoformat() if activation_code.used_at else None,
                    "created_by": activation_code.created_by,
                    "created_at": activation_code.created_at.isoformat() if activation_code.created_at else None,
                    "expires_at": activation_code.expires_at.isoformat() if activation_code.expires_at else None,
                    "batch_id": activation_code.batch_id,
                    "notes": activation_code.notes
                }
            }
        else:
            return {
                "has_used_activation_code": False,
                "activation_code_details": None
            }

    def update_user_activation(self, user_id: str, activation_code: str) -> Dict[str, Any]:
        """
        Update user activation status based on an activation code.

        Args:
            user_id: The user ID to update
            activation_code: The activation code used

        Returns:
            Dict: Updated user information
        """
        if not user_id:
            return {"success": False, "error": "User ID is required"}
        
        if not activation_code:
            return {"success": False, "error": "Activation code is required"}

        try:
            with get_db_session() as session:
                # Find the user
                user = session.query(User).filter(User.user_id == user_id).first()
                
                if not user:
                    return {"success": False, "error": "User not found"}
                
                # Update activation status
                user.is_activated = True
                user.activation_code = activation_code
                user.activated_at = datetime.now()
                
                # Save changes
                session.commit()
                
                # Get activation information
                activation_info = self._get_activation_info(session, user_id)
                
                # Prepare response
                user_data = {
                    "user_id": user.user_id,
                    "display_name": user.display_name,
                    "email": user.email,
                    "profile_picture": user.profile_picture,
                    "is_activated": user.is_activated,
                    "activation_code": user.activation_code,
                    "activated_at": user.activated_at.isoformat() if user.activated_at else None,
                    "user_type": user.user_type,
                    "preferences": user.preferences,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
                
                # Add activation information
                user_data.update(activation_info)
                
                return {
                    "success": True,
                    "user": user_data
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Database error updating user activation {user_id}: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error updating user activation {user_id}: {str(e)}")
            return {"success": False, "error": f"Error: {str(e)}"}

# Create a singleton instance
user_repo = UserRepository()
