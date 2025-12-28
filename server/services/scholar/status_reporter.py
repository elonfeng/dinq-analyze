"""
Status Reporter Module

This module contains functions for reporting status updates during scholar analysis.
It extracts the status reporting logic from the main scholar_service module to improve code clarity.
"""

import time
import logging
from typing import Callable, Dict, Any, Optional, Union

# 获取logger
logger = logging.getLogger('server.services.scholar.status_reporter')


def send_status(message: str, callback: Optional[Callable] = None, progress: Optional[float] = None, **extra_fields) -> None:
    """
    Send a status update message with optional progress information and additional fields.

    Args:
        message: The status message to send
        callback: Optional callback function to receive the message
        progress: Optional progress value (0-100) indicating analysis completion percentage
        **extra_fields: Additional fields to include in the status message (for future extensibility)
    """
    # Format message with progress if provided
    formatted_message = message
    if progress is not None:
        # Ensure progress is between 0 and 100
        progress = max(0, min(100, progress))
        formatted_message = f"[{progress:.1f}%] {message}"
        logger.debug(f"Sending status with progress: {progress:.1f}%")
    
    print(formatted_message)  # Always print for console usage
    
    # If a callback is provided, send either a simple message or a structured message with progress
    if callback:
        # Prepare the structured message with all fields
        status_data = {
            "message": message,
            "progress": progress,
            **extra_fields  # Include any additional fields
        }
        
        # Check if the callback can accept a structured message
        try:
            # First try to pass the complete structured message
            callback(status_data)
        except Exception as e:
            # Log the specific exception for debugging
            logger.debug(f"Structured message callback failed: {str(e)}, falling back to string message")
            # Fall back to just passing the formatted message as a string
            try:
                callback(formatted_message)
            except Exception as e2:
                # If even the fallback fails, log the error but don't crash
                logger.error(f"Failed to send status message: {str(e2)}")


def report_initial_status(researcher_name: str, scholar_id: str, callback: Optional[Callable] = None) -> None:
    """
    Report initial status about the researcher search and ID.

    Args:
        researcher_name: Name of the researcher
        scholar_id: Google Scholar ID
        callback: Optional callback function
    """
    if researcher_name:
        send_status(f"Searching for author: {researcher_name}", callback, progress=5.0)

    if scholar_id:
        send_status(f"Generating report for ID: {scholar_id}...", callback, progress=10.0)


def report_analysis_completion(elapsed_time: float, from_cache: bool, callback: Optional[Callable] = None) -> None:
    """
    Report the completion of the analysis with timing information.

    Args:
        elapsed_time: Time taken for the analysis in seconds
        from_cache: Whether the data was retrieved from cache
        callback: Optional callback function
    """
    cache_info = " (from cache)" if from_cache else ""
    send_status(f"Analysis completed in {elapsed_time:.2f} seconds{cache_info}", callback, progress=100.0)

