"""
Database Utility

This module provides database connection utilities for the user verification system.
Uses the existing MySQL database connection from src/utils/db_utils.py.
"""

import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session

# Configure logging
logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection() -> Generator[Session, None, None]:
    """
    Get database connection context manager using existing MySQL connection

    Yields:
        Session: SQLAlchemy database session
    """
    session = None
    try:
        # Create a new session from the existing session factory
        from src.utils.db_utils import SessionLocal
        session = SessionLocal()
        yield session
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if session:
            session.close()

def init_database():
    """Initialize the database and test connection"""
    try:
        with get_db_connection() as session:
            # Test connection
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).scalar()
            logger.info("Database connection successful")
            return result == 1
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def test_connection():
    """Test database connection"""
    try:
        with get_db_connection() as session:
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).scalar()
            return result == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
