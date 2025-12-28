#!/usr/bin/env python3
"""
Test session fix for user verification system
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_session_fix():
    """Test if the session binding issue is fixed"""
    try:
        print("Testing session fix...")
        
        # Test database connection
        from server.utils.database import test_connection
        if test_connection():
            print("✅ Database connection test passed")
        else:
            print("❌ Database connection test failed")
            return False
        
        # Test service imports
        from server.services.user_verification_service import user_verification_service, email_verification_service
        print("✅ Services imported successfully")
        
        # Test creating a verification record
        test_user_id = "test_session_fix_123"
        
        # Clean up any existing record first
        try:
            existing = user_verification_service.get_user_verification(test_user_id)
            if existing:
                print(f"Found existing record for {test_user_id}")
        except Exception as e:
            print(f"No existing record found: {e}")
        
        # Test creating new verification
        try:
            verification = user_verification_service.create_user_verification(test_user_id, "job_seeker")
            print(f"✅ Created verification record: ID={verification.id}, User={verification.user_id}")
            
            # Test updating the record
            updated = user_verification_service.update_user_verification(test_user_id, {
                "full_name": "Test User",
                "current_role": "Tester"
            })
            print(f"✅ Updated verification record: Name={updated.full_name}, Role={updated.current_role}")
            
            # Test getting the record
            retrieved = user_verification_service.get_user_verification(test_user_id)
            print(f"✅ Retrieved verification record: Name={retrieved.full_name}, Role={retrieved.current_role}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing verification operations: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Error in session fix test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_session_fix()
    if success:
        print("\n🎉 Session fix test passed! The SQLAlchemy session binding issue should be resolved.")
    else:
        print("\n❌ Session fix test failed. Please check the error messages above.")
    
    sys.exit(0 if success else 1)
