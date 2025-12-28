#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Waiting List Repository

This module provides a repository for managing waiting list entries.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy import and_, or_, func
from sqlalchemy.exc import SQLAlchemyError

from src.models.db import WaitingList
from src.utils.db_utils import get_db_session

# Configure logging
logger = logging.getLogger(__name__)

class WaitingListRepository:
    """Repository for managing waiting list entries."""

    def __init__(self):
        """Initialize the repository."""
        pass

    def add_to_waiting_list(self, user_id: str, email: str, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a user to the waiting list or update their entry if they already exist.

        Args:
            user_id: The user ID
            email: The user's email address
            name: The user's full name
            data: Additional data including organization, job_title, reason, and any other metadata

        Returns:
            Dict: Result of the operation
        """
        if not user_id or not email or not name:
            return {"success": False, "error": "User ID, email, and name are required"}

        try:
            with get_db_session() as session:
                # Check if the user is already in the waiting list
                entry = session.query(WaitingList).filter(WaitingList.user_id == user_id).first()

                # Extract standard fields
                organization = data.get('organization')
                job_title = data.get('job_title')
                reason = data.get('reason')

                # Remove standard fields from data to create extra_data
                extra_data = data.copy()
                for field in ['organization', 'job_title', 'reason']:
                    if field in extra_data:
                        del extra_data[field]

                if entry:
                    # Update existing entry
                    entry.email = email
                    entry.name = name
                    entry.organization = organization
                    entry.job_title = job_title
                    entry.reason = reason
                    entry.extra_data = extra_data
                    entry.updated_at = datetime.now()

                    action = "updated"
                else:
                    # Create new entry
                    entry = WaitingList(
                        user_id=user_id,
                        email=email,
                        name=name,
                        organization=organization,
                        job_title=job_title,
                        reason=reason,
                        extra_data=extra_data,
                        status="pending"
                    )
                    session.add(entry)

                    action = "added"

                # Commit changes
                session.commit()

                # Return the entry data
                return {
                    "success": True,
                    "message": f"Successfully {action} to waiting list",
                    "entry": {
                        "id": entry.id,
                        "user_id": entry.user_id,
                        "email": entry.email,
                        "name": entry.name,
                        "organization": entry.organization,
                        "job_title": entry.job_title,
                        "reason": entry.reason,
                        "status": entry.status,
                        "extra_data": entry.extra_data,
                        "created_at": entry.created_at.isoformat() if entry.created_at else None,
                        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None
                    }
                }

        except SQLAlchemyError as e:
            logger.error(f"Database error adding to waiting list: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error adding to waiting list: {str(e)}")
            return {"success": False, "error": f"Error: {str(e)}"}

    def get_waiting_list_entry(self, user_id: str) -> Dict[str, Any]:
        """
        Get a waiting list entry for a user.

        Args:
            user_id: The user ID to get the entry for

        Returns:
            Dict: Waiting list entry or error
        """
        if not user_id:
            return {"success": False, "error": "User ID is required"}

        try:
            with get_db_session() as session:
                # Find the entry
                entry = session.query(WaitingList).filter(WaitingList.user_id == user_id).first()

                if not entry:
                    return {"success": False, "error": "Waiting list entry not found"}

                # Return the entry data
                return {
                    "success": True,
                    "entry": {
                        "id": entry.id,
                        "user_id": entry.user_id,
                        "email": entry.email,
                        "name": entry.name,
                        "organization": entry.organization,
                        "job_title": entry.job_title,
                        "reason": entry.reason,
                        "status": entry.status,
                        "extra_data": entry.extra_data,
                        "created_at": entry.created_at.isoformat() if entry.created_at else None,
                        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                        "approved_at": entry.approved_at.isoformat() if entry.approved_at else None,
                        "approved_by": entry.approved_by
                    }
                }

        except SQLAlchemyError as e:
            logger.error(f"Database error getting waiting list entry: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error getting waiting list entry: {str(e)}")
            return {"success": False, "error": f"Error: {str(e)}"}

    def update_entry_status(self, user_id: str, status: str, approved_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Update the status of a waiting list entry.

        Args:
            user_id: The user ID of the entry to update
            status: The new status (pending, approved, rejected)
            approved_by: The user ID who approved the entry (required if status is 'approved')

        Returns:
            Dict: Result of the operation
        """
        if not user_id:
            return {"success": False, "error": "User ID is required"}

        if status not in ["pending", "approved", "rejected"]:
            return {"success": False, "error": "Invalid status. Must be one of: pending, approved, rejected"}

        if status == "approved" and not approved_by:
            return {"success": False, "error": "approved_by is required when status is 'approved'"}

        try:
            with get_db_session() as session:
                # Find the entry
                entry = session.query(WaitingList).filter(WaitingList.user_id == user_id).first()

                if not entry:
                    return {"success": False, "error": "Waiting list entry not found"}

                # Update status
                entry.status = status

                # Update approval information if approved
                if status == "approved":
                    entry.approved_at = datetime.now()
                    entry.approved_by = approved_by

                # Commit changes
                session.commit()

                # Return the updated entry
                return {
                    "success": True,
                    "message": f"Successfully updated status to '{status}'",
                    "entry": {
                        "id": entry.id,
                        "user_id": entry.user_id,
                        "email": entry.email,
                        "name": entry.name,
                        "status": entry.status,
                        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                        "approved_at": entry.approved_at.isoformat() if entry.approved_at else None,
                        "approved_by": entry.approved_by
                    }
                }

        except SQLAlchemyError as e:
            logger.error(f"Database error updating waiting list entry: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error updating waiting list entry: {str(e)}")
            return {"success": False, "error": f"Error: {str(e)}"}

    def get_waiting_list(self, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Get waiting list entries with optional filtering.

        Args:
            status: Filter by status (pending, approved, rejected)
            limit: Maximum number of entries to return
            offset: Offset for pagination

        Returns:
            Dict: List of waiting list entries
        """
        try:
            with get_db_session() as session:
                # Build query
                query = session.query(WaitingList)

                # Apply status filter if provided
                if status:
                    if status not in ["pending", "approved", "rejected"]:
                        return {"success": False, "error": "Invalid status. Must be one of: pending, approved, rejected"}

                    query = query.filter(WaitingList.status == status)

                # Get total count
                total_count = query.count()

                # Apply pagination
                query = query.order_by(WaitingList.created_at.desc())
                query = query.limit(limit).offset(offset)

                # Execute query
                entries = query.all()

                # Format results
                results = []
                for entry in entries:
                    results.append({
                        "id": entry.id,
                        "user_id": entry.user_id,
                        "email": entry.email,
                        "name": entry.name,
                        "organization": entry.organization,
                        "job_title": entry.job_title,
                        "reason": entry.reason,
                        "status": entry.status,
                        "extra_data": entry.extra_data,
                        "created_at": entry.created_at.isoformat() if entry.created_at else None,
                        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                        "approved_at": entry.approved_at.isoformat() if entry.approved_at else None,
                        "approved_by": entry.approved_by
                    })

                # Return results
                return {
                    "success": True,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "entries": results
                }

        except SQLAlchemyError as e:
            logger.error(f"Database error getting waiting list: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error getting waiting list: {str(e)}")
            return {"success": False, "error": f"Error: {str(e)}"}

# Create a singleton instance
waiting_list_repo = WaitingListRepository()
