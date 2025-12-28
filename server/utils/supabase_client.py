"""
Supabase Client Utility

This module provides a Supabase client for interacting with Supabase services.
"""

import os
import logging
from typing import Any, Optional

try:
    from supabase import create_client, Client  # type: ignore
except Exception:  # noqa: BLE001
    create_client = None
    Client = Any  # type: ignore

# Configure logging
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = "https://rlkbxuuszlscnwagrsyx.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJsa2J4dXVzemxzY253YWdyc3l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ3NjYyNTMsImV4cCI6MjA2MDM0MjI1M30.gzLgVjao2cNG2qOgaVEObVO42tnHWZsPJB1uCTSbFUc"

# Global client instance
_supabase_client: Optional[Any] = None

def get_supabase_client() -> Client:
    """
    Get or create a Supabase client instance.

    Returns:
        Supabase client instance
    """
    global _supabase_client

    if create_client is None:
        raise RuntimeError("Supabase SDK not installed. Install with `pip install supabase`.")

    if _supabase_client is None:
        try:
            # Create Supabase client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise

    return _supabase_client

def test_supabase_connection() -> bool:
    """
    Test the Supabase connection.

    Returns:
        True if connection is successful, False otherwise
    """
    try:
        client = get_supabase_client()
        # Try to list buckets to test the connection
        response = client.storage.list_buckets()
        # Check if response is a list (success) or has an error attribute
        if hasattr(response, 'error') and response.error:
            logger.error(f"Supabase connection test failed: {response.error}")
            return False
        elif isinstance(response, list):
            logger.info("Supabase connection test successful")
            return True
        else:
            logger.info("Supabase connection test successful")
            return True
    except Exception as e:
        logger.error(f"Supabase connection test failed: {e}")
        return False

def create_bucket_if_not_exists(bucket_name: str, public: bool = True) -> bool:
    """
    Create a storage bucket if it doesn't exist.

    Args:
        bucket_name: Name of the bucket to create
        public: Whether the bucket should be public

    Returns:
        True if bucket exists or was created successfully, False otherwise
    """
    try:
        client = get_supabase_client()

        # Check if bucket exists
        buckets_response = client.storage.list_buckets()

        # Handle different response formats
        if hasattr(buckets_response, 'error') and buckets_response.error:
            logger.error(f"Failed to list buckets: {buckets_response.error}")
            return False

        # Extract bucket list
        if hasattr(buckets_response, 'data'):
            buckets_list = buckets_response.data
        elif isinstance(buckets_response, list):
            buckets_list = buckets_response
        else:
            logger.error(f"Unexpected response format: {type(buckets_response)}")
            return False

        existing_buckets = [bucket.name if hasattr(bucket, 'name') else bucket.get('name', '') for bucket in buckets_list]

        if bucket_name in existing_buckets:
            logger.info(f"Bucket '{bucket_name}' already exists")
            return True

        # Create bucket
        try:
            # Use the correct API format for creating bucket
            create_response = client.storage.create_bucket(bucket_name)
            if hasattr(create_response, 'error') and create_response.error:
                logger.error(f"Failed to create bucket '{bucket_name}': {create_response.error}")
                return False

            logger.info(f"Bucket '{bucket_name}' created successfully")
            return True
        except Exception as create_error:
            logger.error(f"Error creating bucket '{bucket_name}': {create_error}")
            # If bucket creation fails, it might already exist, so let's check again
            return bucket_name in existing_buckets

    except Exception as e:
        logger.error(f"Error creating bucket '{bucket_name}': {e}")
        return False

def get_public_url(bucket_name: str, file_path: str) -> Optional[str]:
    """
    Get the public URL for a file in Supabase storage.

    Args:
        bucket_name: Name of the storage bucket
        file_path: Path to the file within the bucket

    Returns:
        Public URL string if successful, None otherwise
    """
    try:
        client = get_supabase_client()
        public_url = client.storage.from_(bucket_name).get_public_url(file_path)
        return public_url
    except Exception as e:
        logger.error(f"Error getting public URL for {bucket_name}/{file_path}: {e}")
        return None
