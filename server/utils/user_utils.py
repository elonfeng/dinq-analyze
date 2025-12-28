"""
User Utilities

This module provides utility functions for working with authenticated users.
"""

from flask import g

def get_current_user_id() -> str:
    """
    Get the ID of the currently authenticated user.

    This function should be called from within a route handler that is
    decorated with the @require_auth decorator.

    Returns:
        str: The user ID of the authenticated user, or 'anonymous' if no user is authenticated.
    """
    return getattr(g, 'user_id', 'anonymous')

def is_authenticated() -> bool:
    """
    Check if the current request is authenticated.

    Returns:
        bool: True if the request is authenticated, False otherwise.
    """
    return hasattr(g, 'user_id') and g.user_id != 'anonymous'

def is_verified_user() -> bool:
    """
    Check if the current user is a verified user.
    This is stricter than is_authenticated() and checks if the user has been
    verified through Firebase authentication.

    Returns:
        bool: True if the user is verified, False otherwise.
    """
    return hasattr(g, 'is_verified_user') and g.is_verified_user is True
