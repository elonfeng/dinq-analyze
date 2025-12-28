#!/usr/bin/env python3
"""
Create User Verification Tables

This script creates the user verification tables in the MySQL database.
"""

import os
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.utils.db_utils import engine
from src.models.user_verification import Base
from server.utils.logging_config import setup_logging
import logging

def main():
    """Create the verification tables"""
    # Setup logging
    logger = setup_logging()
    logger = logging.getLogger(__name__)
    
    print("Creating User Verification Tables...")
    
    try:
        # Create all tables defined in the models
        Base.metadata.create_all(engine)
        print("✅ User verification tables created successfully!")
        
        # Test database connection
        from server.services.user_verification_service import user_verification_service
        stats = user_verification_service.get_verification_stats()
        print(f"✅ Database connection test successful!")
        print(f"Current stats: {stats}")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        logger.error(f"Table creation failed: {e}")
        return False
    
    print("\nTable creation completed!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
