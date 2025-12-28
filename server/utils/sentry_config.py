"""
Sentry Configuration

This module provides Sentry integration for error monitoring and performance tracking.
It initializes the Sentry SDK and configures it for use with Flask.
"""

import os
import logging
from typing import Optional, Dict, Any

# Try to import Sentry SDK
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

# Set up logger
logger = logging.getLogger(__name__)

def before_send_log(log: 'Log', hint: 'Hint') -> Optional['Log']:
    """Add custom trace ID to Sentry logs before sending."""
    try:
        from server.utils.trace_context import TraceContext
        custom_trace_id = TraceContext.get_trace_id()

        if custom_trace_id:
            if 'attributes' not in log:
                log['attributes'] = {}
            log['attributes']['dinq_trace_id'] = custom_trace_id
    except:
        pass

    return log

def init_sentry(dsn: Optional[str] = None,
                environment: Optional[str] = None,
                traces_sample_rate: float = 0.1,
                profiles_sample_rate: float = 0.1,
                send_default_pii: bool = False,
                extra_config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Initialize Sentry SDK for error monitoring and performance tracking.

    Args:
        dsn: Sentry DSN (Data Source Name). If None, uses SENTRY_DSN from environment.
        environment: Environment name (e.g., 'production', 'staging', 'development').
            If None, uses SENTRY_ENVIRONMENT from environment or defaults to 'development'.
        traces_sample_rate: Percentage of transactions to sample for performance monitoring (0.0 to 1.0).
        profiles_sample_rate: Percentage of transactions to sample for profiling (0.0 to 1.0).
        send_default_pii: Whether to send personally identifiable information (PII) to Sentry.
        extra_config: Additional configuration options to pass to Sentry.

    Returns:
        bool: True if Sentry was successfully initialized, False otherwise.
    """
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not available. Install with 'pip install sentry-sdk[flask]'")
        return False

    # Get DSN from environment if not provided
    if dsn is None:
        dsn = os.environ.get('SENTRY_DSN')
        if not dsn:
            logger.warning("Sentry DSN not provided and SENTRY_DSN not set in environment. Sentry will not be initialized.")
            return False

    # Get environment from environment variable if not provided
    if environment is None:
        environment = os.environ.get('SENTRY_ENVIRONMENT', 'development')

    # Set up logging integration
    logging_integration = LoggingIntegration(
        level=logging.INFO,      # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors as events
    )

    # Initialize Sentry SDK
    try:
        config = {
            'dsn': dsn,
            'environment': environment,
            'integrations': [
                FlaskIntegration(),
                logging_integration,
            ],
            'traces_sample_rate': traces_sample_rate,
            'profiles_sample_rate': profiles_sample_rate,
            'send_default_pii': send_default_pii,
            'profile_lifecycle': "trace",  # Automatically run profiler when there is an active transaction
            '_experiments': {
                'enable_logs': True,
                'before_send_log': before_send_log,
            },
        }

        # Add any extra configuration
        if extra_config:
            config.update(extra_config)

        sentry_sdk.init(**config)

        logger.info(f"Sentry initialized successfully for environment: {environment}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {str(e)}")
        return False

def capture_message(message: str, level: str = "info", **kwargs) -> None:
    """
    Capture a message in Sentry.

    Args:
        message: The message to capture
        level: The level of the message ('info', 'warning', 'error', 'fatal')
        **kwargs: Additional keyword arguments to pass to sentry_sdk.capture_message
    """
    if not SENTRY_AVAILABLE:
        logger.warning(f"Sentry SDK not available. Message not captured: {message}")
        return

    try:
        sentry_sdk.capture_message(message, level=level, **kwargs)
    except Exception as e:
        logger.error(f"Failed to capture message in Sentry: {str(e)}")

def capture_exception(exc: Optional[Exception] = None, **kwargs) -> None:
    """
    Capture an exception in Sentry.

    Args:
        exc: The exception to capture. If None, captures the current exception.
        **kwargs: Additional keyword arguments to pass to sentry_sdk.capture_exception
    """
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not available. Exception not captured.")
        return

    try:
        sentry_sdk.capture_exception(exc, **kwargs)
    except Exception as e:
        logger.error(f"Failed to capture exception in Sentry: {str(e)}")

def set_user(user_info: Dict[str, Any]) -> None:
    """
    Set user information for Sentry events.

    Args:
        user_info: Dictionary containing user information (id, username, email, etc.)
    """
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not available. User context not set.")
        return

    try:
        sentry_sdk.set_user(user_info)
    except Exception as e:
        logger.error(f"Failed to set user context in Sentry: {str(e)}")

def set_tag(key: str, value: str) -> None:
    """
    Set a tag for Sentry events.

    Args:
        key: Tag key
        value: Tag value
    """
    if not SENTRY_AVAILABLE:
        logger.warning(f"Sentry SDK not available. Tag not set: {key}={value}")
        return

    try:
        sentry_sdk.set_tag(key, value)
    except Exception as e:
        logger.error(f"Failed to set tag in Sentry: {str(e)}")
