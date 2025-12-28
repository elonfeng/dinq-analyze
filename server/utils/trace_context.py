"""
Request Tracing Context

This module provides request tracing functionality with unique trace IDs
for each HTTP request. It handles thread-local storage and context propagation
across different threads and async operations.
"""

import uuid
import threading
import logging
from typing import Optional, Dict, Any
from contextvars import ContextVar
from flask import g, request, has_request_context

# Context variable for trace ID (Python 3.7+)
# This automatically handles thread switching and async operations
trace_id_context: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)

# Thread-local storage as fallback for older Python versions or special cases
_thread_local = threading.local()

class TraceContext:
    """
    Manages trace context for request tracking.

    This class provides methods to generate, set, and retrieve trace IDs
    that persist across thread boundaries and async operations.
    """

    @staticmethod
    def generate_trace_id() -> str:
        """
        Generate a new unique trace ID.

        Returns:
            A unique trace ID string
        """
        return str(uuid.uuid4())[:8]  # Use first 8 characters for readability

    @staticmethod
    def set_trace_id(trace_id: str) -> None:
        """
        Set the trace ID for the current context.

        Args:
            trace_id: The trace ID to set
        """
        # Set in context variable (preferred method)
        trace_id_context.set(trace_id)

        # Set in thread-local storage as fallback
        _thread_local.trace_id = trace_id

        # Set in Flask's g object if available
        if has_request_context():
            g.trace_id = trace_id

    @staticmethod
    def get_trace_id() -> Optional[str]:
        """
        Get the current trace ID.

        Returns:
            The current trace ID or None if not set
        """
        # Try context variable first (handles async and thread switching)
        trace_id = trace_id_context.get()
        if trace_id:
            return trace_id

        # Try Flask's g object
        if has_request_context() and hasattr(g, 'trace_id'):
            return g.trace_id

        # Try thread-local storage as fallback
        return getattr(_thread_local, 'trace_id', None)

    @staticmethod
    def clear_trace_id() -> None:
        """Clear the trace ID from all contexts."""
        trace_id_context.set(None)
        if hasattr(_thread_local, 'trace_id'):
            delattr(_thread_local, 'trace_id')
        if has_request_context() and hasattr(g, 'trace_id'):
            delattr(g, 'trace_id')

    @staticmethod
    def get_or_create_trace_id() -> str:
        """
        Get the current trace ID or create a new one if none exists.

        Returns:
            The current or newly created trace ID
        """
        trace_id = TraceContext.get_trace_id()
        if not trace_id:
            trace_id = TraceContext.generate_trace_id()
            TraceContext.set_trace_id(trace_id)
        return trace_id

    @staticmethod
    def get_request_info() -> Dict[str, Any]:
        """
        Get additional request information for logging.

        Returns:
            Dictionary with request information
        """
        info = {}

        if has_request_context():
            info.update({
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'Unknown')[:100],  # Truncate long user agents
            })

            # Add user ID if available
            if hasattr(g, 'user_id') and g.user_id:
                info['user_id'] = g.user_id

            # Add custom headers that might be useful
            userid_header = request.headers.get('Userid') or request.headers.get('userid')
            if userid_header:
                info['userid_header'] = userid_header

        return info

class TraceLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes trace ID in log messages.

    This adapter ensures that every log message includes the current trace ID
    and additional request context information.
    """

    def process(self, msg, kwargs):
        """
        Process the log message to include trace information.

        Args:
            msg: The log message
            kwargs: Additional keyword arguments

        Returns:
            Tuple of (message, kwargs) with trace information added
        """
        # Get trace ID
        trace_id = TraceContext.get_trace_id()

        # Get request information
        request_info = TraceContext.get_request_info()

        # Build extra information
        extra = kwargs.get('extra', {})

        if trace_id:
            extra['trace_id'] = trace_id

        # Add request information
        extra.update(request_info)

        kwargs['extra'] = extra

        return msg, kwargs

def get_trace_logger(name: str) -> TraceLoggerAdapter:
    """
    Get a logger with automatic trace ID inclusion.

    Args:
        name: The logger name

    Returns:
        A TraceLoggerAdapter instance
    """
    logger = logging.getLogger(name)
    adapter = TraceLoggerAdapter(logger, {})
    # 添加一个属性来访问底层的logger，以便需要时可以添加handler
    adapter.logger = logger
    return adapter

def get_real_logger(name: str) -> logging.Logger:
    """
    Get the real logger object for cases where you need to add handlers.

    Args:
        name: The logger name

    Returns:
        The real logging.Logger instance
    """
    return logging.getLogger(name)

def propagate_trace_to_thread(target_func, *args, **kwargs):
    """
    Wrapper function to propagate trace context to new threads.

    Args:
        target_func: The target function to run in the new thread
        *args: Arguments for the target function
        **kwargs: Keyword arguments for the target function

    Returns:
        The result of the target function
    """
    # Capture current trace ID
    current_trace_id = TraceContext.get_trace_id()

    def wrapper():
        # Set trace ID in the new thread
        if current_trace_id:
            TraceContext.set_trace_id(current_trace_id)

        try:
            return target_func(*args, **kwargs)
        finally:
            # Clean up trace ID when thread finishes
            TraceContext.clear_trace_id()

    return wrapper

# Convenience functions for common operations
def start_trace(trace_id: Optional[str] = None) -> str:
    """
    Start a new trace or continue an existing one.

    Args:
        trace_id: Optional existing trace ID to continue

    Returns:
        The trace ID being used
    """
    if trace_id:
        TraceContext.set_trace_id(trace_id)
        return trace_id
    else:
        return TraceContext.get_or_create_trace_id()

def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID."""
    return TraceContext.get_trace_id()

def end_trace() -> None:
    """End the current trace."""
    TraceContext.clear_trace_id()
