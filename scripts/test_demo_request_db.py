"""
Test Demo Request Database

This script tests the demo request database functionality directly.
"""

import sys
import os
import logging
from datetime import datetime

# Add the project root to the Python path to enable absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import database models and utilities
from src.models.user_interactions import DemoRequest
from src.utils.db_utils import get_db_session

def test_create_demo_request():
    """Test creating a demo request directly in the database."""
    logger.info("Testing demo request creation...")
    
    # Test user ID
    user_id = "gAckWxWYazcI5k95n627hRBHB712"
    
    # Test data
    test_data = {
        "email": "direct_test@example.com",
        "affiliation": "Direct Test University",
        "country": "United States",
        "job_title": "Database Tester",
        "contact_reason": "Testing database connection",
        "additional_details": "This is a direct database test",
        "marketing_consent": True
    }
    
    try:
        with get_db_session() as session:
            # Create demo request
            demo_request = DemoRequest(
                user_id=user_id,
                email=test_data["email"],
                affiliation=test_data["affiliation"],
                country=test_data["country"],
                job_title=test_data["job_title"],
                contact_reason=test_data["contact_reason"],
                additional_details=test_data["additional_details"],
                marketing_consent=test_data["marketing_consent"],
                status="pending",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Add to session
            session.add(demo_request)
            session.commit()
            
            # Get ID
            logger.info(f"Created demo request with ID: {demo_request.id}")
            
            # Verify by querying
            result = session.query(DemoRequest).filter(DemoRequest.id == demo_request.id).first()
            
            if result:
                logger.info(f"Successfully verified demo request: {result}")
                logger.info(f"Email: {result.email}")
                logger.info(f"Affiliation: {result.affiliation}")
                return True
            else:
                logger.error("Failed to verify demo request")
                return False
    except Exception as e:
        logger.error(f"Error creating demo request: {e}")
        return False

def test_get_demo_requests():
    """Test retrieving demo requests from the database."""
    logger.info("Testing demo request retrieval...")
    
    try:
        with get_db_session() as session:
            # Get all demo requests
            requests = session.query(DemoRequest).all()
            
            logger.info(f"Found {len(requests)} demo requests:")
            
            for req in requests:
                logger.info(f"ID: {req.id}, Email: {req.email}, User: {req.user_id}")
            
            return True
    except Exception as e:
        logger.error(f"Error retrieving demo requests: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting demo request database tests...")
    
    # Test creating a demo request
    create_success = test_create_demo_request()
    
    # Test retrieving demo requests
    get_success = test_get_demo_requests()
    
    if create_success and get_success:
        logger.info("All tests completed successfully!")
    else:
        logger.error("Some tests failed.")
