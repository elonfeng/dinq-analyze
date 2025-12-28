"""
Firebase Configuration

This module provides Firebase integration for authentication.
It initializes the Firebase Admin SDK and provides functions for verifying tokens.

Usage:
    from server.config.firebase_config import firebase_auth

    # Verify a token
    decoded_token = firebase_auth.verify_id_token(id_token)
    uid = decoded_token['uid']
"""

import os
import sys
import logging
from typing import Optional, Dict, Any

# Import environment variable loader
try:
    from server.config.env_loader import load_environment_variables
    # Load environment variables
    load_environment_variables()
except ImportError:
    # Fallback to simple dotenv loading
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

# Set up logger
logger = logging.getLogger(__name__)

# Try to import Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("Firebase Admin SDK not available. Install with 'pip install firebase-admin'")

# Firebase Admin SDK instance
firebase_app = None
firebase_auth = None

def init_firebase(service_account_path: Optional[str] = None) -> bool:
    """
    Initialize Firebase Admin SDK for authentication.

    Args:
        service_account_path: Path to the Firebase service account JSON file.
                             If None, will try to load from environment variable or use default path.

    Returns:
        bool: True if Firebase was successfully initialized, False otherwise.
    """
    global firebase_app, firebase_auth

    if not FIREBASE_AVAILABLE:
        logger.warning("Firebase Admin SDK not available. Install with 'pip install firebase-admin'")
        logger.warning("Checking if firebase-admin is installed...")
        try:
            import pkg_resources
            installed_packages = {pkg.key for pkg in pkg_resources.working_set}
            if 'firebase-admin' in installed_packages:
                logger.warning("firebase-admin is installed but could not be imported. This might be a path or version issue.")
                logger.warning(f"Python path: {sys.path}")
                logger.warning(f"Current working directory: {os.getcwd()}")
            else:
                logger.warning("firebase-admin is not installed. Please install it with 'pip install firebase-admin'")
        except ImportError:
            logger.warning("Could not check installed packages")
        return False

    # If Firebase is already initialized, return True
    if firebase_app is not None:
        logger.info("Firebase already initialized")
        return True

    try:
        # Get service account path from environment if not provided
        if service_account_path is None:
            # First try to get from environment variable
            service_account_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')
            if service_account_path:
                logger.info(f"Using Firebase service account path from environment: {service_account_path}")
            else:
                logger.warning("FIREBASE_SERVICE_ACCOUNT_PATH not set in environment")

            # If not in environment, use default paths
            if not service_account_path:
                # Try multiple possible locations
                possible_paths = []

                # 1. Get the directory of the current file
                current_dir = os.path.dirname(os.path.abspath(__file__))
                server_dir = os.path.dirname(current_dir)
                project_dir = os.path.dirname(server_dir)

                # 2. Add possible paths
                possible_paths.append(os.path.join(server_dir, 'secrets', 'firebase-adminsdk.json'))
                possible_paths.append(os.path.join(project_dir, 'secrets', 'firebase-adminsdk.json'))
                possible_paths.append(os.path.join(project_dir, 'firebase-adminsdk.json'))
                possible_paths.append(os.path.join(os.getcwd(), 'firebase-adminsdk.json'))

                # 3. Log the paths we're checking
                logger.info(f"Checking for Firebase service account in the following locations:")
                for path in possible_paths:
                    logger.info(f"  - {path}")

                # 4. Check each path
                for path in possible_paths:
                    if os.path.exists(path):
                        service_account_path = path
                        logger.info(f"Found Firebase service account at: {path}")
                        break

                if not service_account_path:
                    logger.warning("Could not find Firebase service account file in any of the checked locations")

        # Initialize with service account if provided
        if service_account_path:
            if os.path.exists(service_account_path):
                logger.info(f"Initializing Firebase with service account: {service_account_path}")
                cred = credentials.Certificate(service_account_path)
                firebase_app = firebase_admin.initialize_app(cred)
                firebase_auth = auth
                logger.info(f"Firebase successfully initialized with service account")
                return True
            else:
                logger.error(f"Firebase service account file not found at: {service_account_path}")
                return False

        # Try to initialize with application default credentials
        logger.info("Attempting to initialize Firebase with application default credentials")
        firebase_app = firebase_admin.initialize_app()
        firebase_auth = auth
        logger.info("Firebase successfully initialized with application default credentials")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

# Check if we should skip authentication in development/test mode
flask_env = os.environ.get("FLASK_ENV", "development").lower()
is_production = flask_env == "production"
is_dev_env = flask_env == "development"
is_test_env = flask_env in ("test", "testing", "ci")

skip_auth_in_dev = os.environ.get("FIREBASE_SKIP_AUTH_IN_DEV", "false").lower() == "true"

# Test/CI bypass: if auth is bypassed, don't initialize Firebase (never allow in production).
auth_bypass = os.environ.get("DINQ_AUTH_BYPASS", "false").lower() in ("1", "true", "yes", "on")
will_skip_auth = (is_dev_env and skip_auth_in_dev) or is_test_env or (auth_bypass and not is_production)

logger.info(
    "Firebase configuration: env=%s, dev=%s, test=%s, skip_auth_in_dev=%s, auth_bypass=%s",
    flask_env,
    is_dev_env,
    is_test_env,
    skip_auth_in_dev,
    auth_bypass,
)
logger.info("Will %s Firebase authentication", "skip" if will_skip_auth else "NOT skip")

if will_skip_auth:
    logger.info("Skipping Firebase initialization")
    firebase_initialized = True  # Pretend it's initialized
else:
    logger.info("Initializing Firebase authentication")
    firebase_initialized = init_firebase()
    if not firebase_initialized:
        logger.warning(
            "Firebase authentication is not available. "
            "Set FIREBASE_SERVICE_ACCOUNT_PATH in environment or provide service account path to init_firebase()."
        )
