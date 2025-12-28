"""
Sentry Handler Module

This module provides handlers for Sentry-related API endpoints,
including health checks and alert webhooks.
"""

import time
import logging
import json
from flask import request, jsonify, Blueprint

# Set up logger
logger = logging.getLogger(__name__)

# Create a Blueprint for Sentry-related routes
sentry_bp = Blueprint('sentry', __name__)

# Store reference to whether Sentry is initialized
sentry_initialized = False

def configure_sentry_handler(is_sentry_initialized):
    """
    Configure the Sentry handler with initialization status.
    
    Args:
        is_sentry_initialized: Boolean indicating if Sentry is initialized
    """
    global sentry_initialized
    sentry_initialized = is_sentry_initialized
    logger.info(f"Sentry handler configured. Sentry initialized: {sentry_initialized}")

@sentry_bp.route('/api/alert', methods=['POST', 'OPTIONS'])
def sentry_alert_api():
    """
    Handle Sentry alert webhook requests.
    
    This endpoint receives health check and alert notifications from Sentry.
    These are periodic requests sent by Sentry to verify the connection and monitor the application.
    """
    # Handle OPTIONS requests
    if request.method == 'OPTIONS':
        # This will be handled by the CORS handler in app.py
        return jsonify({"status": "options_handled"})
        
    try:
        # Log the request details
        data = request.get_json(silent=True) or {}
        headers = dict(request.headers)
        
        # Remove sensitive information from headers before logging
        if 'Authorization' in headers:
            headers['Authorization'] = '[REDACTED]'
            
        # Log detailed information about the request
        logger.info(f"Received Sentry alert webhook: {request.path}")
        logger.debug(f"Sentry alert headers: {headers}")
        logger.debug(f"Sentry alert data: {data}")
        
        # If Sentry is initialized, add this event to Sentry for monitoring
        if sentry_initialized:
            try:
                from server.utils.sentry_config import capture_message, set_tag
                set_tag('webhook_type', 'sentry_alert')
                capture_message("Received Sentry alert webhook", level="info")
            except ImportError:
                logger.warning("Could not import Sentry utilities")
        
        # Return a success response
        return jsonify({
            "status": "success",
            "message": "Alert received",
            "timestamp": time.time()
        })
    except Exception as e:
        logger.error(f"Error processing Sentry alert: {str(e)}")
        if sentry_initialized:
            try:
                from server.utils.sentry_config import capture_exception
                capture_exception(e)
            except ImportError:
                logger.warning("Could not import Sentry utilities")
        return jsonify({"error": str(e)}), 500
