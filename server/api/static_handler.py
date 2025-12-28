"""
Static Handler API

This module handles static file requests and responses.
"""

import os
import mimetypes
from typing import Tuple, Optional


def get_static_file_path(request_path: str, static_root: str) -> str:
    """
    Get the absolute path to a static file based on the request path.
    
    Args:
        request_path: The path requested by the client
        static_root: The root directory for static files
        
    Returns:
        Absolute path to the static file
    """
    # Remove any leading slashes and normalize the path
    normalized_path = request_path.lstrip('/')
    
    # Handle the case where the path is empty (root path)
    if not normalized_path:
        normalized_path = 'index.html'
    
    # Construct the absolute path to the static file
    absolute_path = os.path.join(static_root, normalized_path)
    
    return absolute_path


def get_mime_type(file_path: str) -> str:
    """
    Get the MIME type for a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string
    """
    # Get the MIME type based on the file extension
    mime_type, _ = mimetypes.guess_type(file_path)
    
    # Default to 'application/octet-stream' if the MIME type cannot be determined
    if mime_type is None:
        mime_type = 'application/octet-stream'
    
    return mime_type


def read_static_file(file_path: str) -> Tuple[Optional[bytes], Optional[str], int]:
    """
    Read a static file and return its contents, MIME type, and status code.
    
    Args:
        file_path: Path to the static file
        
    Returns:
        Tuple containing:
        - File contents as bytes (or None if file not found)
        - MIME type (or None if file not found)
        - HTTP status code (200 for success, 404 for not found)
    """
    # Check if the file exists
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return None, None, 404
    
    # Get the MIME type
    mime_type = get_mime_type(file_path)
    
    # Read the file contents
    with open(file_path, 'rb') as file:
        file_contents = file.read()
    
    return file_contents, mime_type, 200
