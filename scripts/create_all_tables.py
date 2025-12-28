"""
Create All Database Tables

This script creates all database tables defined in the models.
"""

import sys
import os
import logging

# Add the project root to the Python path to enable absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import all models to ensure they are registered with the Base metadata
from src.models.db import Base, ApiUsage, Scholar
from src.models.job_board import JobPost
from src.models.user_interactions import JobPostLike, JobPostBookmark, DemoRequest

# Import database utilities
from src.utils.db_utils import create_tables

if __name__ == "__main__":
    logger.info("Starting database table creation...")
    
    # Create all tables
    success = create_tables()
    
    if success:
        logger.info("All database tables created successfully.")
    else:
        logger.error("Failed to create database tables.")
