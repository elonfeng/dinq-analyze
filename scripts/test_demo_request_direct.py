"""
Test Demo Request Direct

This script tests the demo request functionality directly using the database.
"""

import sys
import os
import logging
import json
from datetime import datetime

# Add the project root to the Python path to enable absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import database models and utilities
from src.models.user_interactions import DemoRequest
from src.utils.db_utils import get_db_session

def create_demo_request():
    """Create a demo request directly in the database."""
    logger.info("Creating a demo request...")
    
    # Test user ID
    user_id = "gAckWxWYazcI5k95n627hRBHB712"
    
    # Test data
    data = {
        "email": "test_direct@example.com",
        "affiliation": "Test University",
        "country": "United States",
        "job_title": "Researcher",
        "contact_reason": "Interested in using the product for research",
        "additional_details": "Would like to know more about pricing and features",
        "marketing_consent": True
    }
    
    try:
        with get_db_session() as session:
            # Create the demo request object
            demo_request = DemoRequest(
                user_id=user_id,
                email=data.get('email'),
                affiliation=data.get('affiliation'),
                country=data.get('country'),
                job_title=data.get('job_title'),
                contact_reason=data.get('contact_reason'),
                additional_details=data.get('additional_details'),
                marketing_consent=data.get('marketing_consent', False),
                status="pending",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Add to session
            session.add(demo_request)
            session.commit()
            
            # Convert to dictionary for response
            result = {
                'id': demo_request.id,
                'user_id': demo_request.user_id,
                'email': demo_request.email,
                'affiliation': demo_request.affiliation,
                'country': demo_request.country,
                'job_title': demo_request.job_title,
                'contact_reason': demo_request.contact_reason,
                'additional_details': demo_request.additional_details,
                'marketing_consent': demo_request.marketing_consent,
                'status': demo_request.status,
                'created_at': demo_request.created_at.isoformat() if demo_request.created_at else None,
                'updated_at': demo_request.updated_at.isoformat() if demo_request.updated_at else None
            }
            
            logger.info(f"Created demo request with ID: {demo_request.id}")
            logger.info(f"Result: {json.dumps(result, indent=2)}")
            
            return result
    except Exception as e:
        logger.error(f"Error creating demo request: {e}")
        return None

def get_demo_requests():
    """Get all demo requests from the database."""
    logger.info("Getting all demo requests...")
    
    try:
        with get_db_session() as session:
            # Get all demo requests
            requests = session.query(DemoRequest).all()
            
            # Convert to dictionaries
            results = []
            for req in requests:
                result = {
                    'id': req.id,
                    'user_id': req.user_id,
                    'email': req.email,
                    'affiliation': req.affiliation,
                    'country': req.country,
                    'job_title': req.job_title,
                    'contact_reason': req.contact_reason,
                    'additional_details': req.additional_details,
                    'marketing_consent': req.marketing_consent,
                    'status': req.status,
                    'created_at': req.created_at.isoformat() if req.created_at else None,
                    'updated_at': req.updated_at.isoformat() if req.updated_at else None
                }
                results.append(result)
            
            logger.info(f"Found {len(results)} demo requests")
            for i, result in enumerate(results):
                logger.info(f"Request {i+1}: ID={result['id']}, Email={result['email']}")
            
            return results
    except Exception as e:
        logger.error(f"Error getting demo requests: {e}")
        return []

if __name__ == "__main__":
    logger.info("Starting direct demo request test...")
    
    # Create a demo request
    create_result = create_demo_request()
    
    if create_result:
        logger.info("Demo request created successfully!")
    else:
        logger.error("Failed to create demo request")
    
    # Get all demo requests
    get_results = get_demo_requests()
    
    if get_results:
        logger.info(f"Successfully retrieved {len(get_results)} demo requests")
    else:
        logger.error("Failed to retrieve demo requests")
    
    logger.info("Test completed")
