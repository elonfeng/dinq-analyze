"""
Initialize Demo Requests Table

This script creates the demo_requests table in the database.
"""

import sys
import os
import logging

# Add the project root to the Python path to enable absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import database models and utilities
from src.models.db import Base
from src.models.user_interactions import DemoRequest
from src.utils.db_utils import engine, create_tables

def init_demo_requests_table():
    """Initialize the demo_requests table."""
    try:
        # Create the demo_requests table
        logger.info("Creating demo_requests table...")
        
        # Create the table using SQLAlchemy's metadata
        DemoRequest.__table__.create(engine, checkfirst=True)
        
        logger.info("Demo requests table created successfully.")
        return True
    except Exception as e:
        logger.error(f"Error creating demo_requests table: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database initialization...")
    
    # Initialize the demo_requests table
    success = init_demo_requests_table()
    
    if success:
        logger.info("Database initialization completed successfully.")
    else:
        logger.error("Database initialization failed.")
