"""
Configuration Package

This package contains configuration modules for the DINQ project.
"""

from server.config.api_keys import API_KEYS
from server.config.env_loader import load_environment_variables, get_env_var, log_dinq_environment_variables

# Import Firebase configuration
try:
    from server.config.firebase_config import firebase_auth, firebase_initialized
    __all__ = ['API_KEYS', 'firebase_auth', 'firebase_initialized', 'load_environment_variables', 'get_env_var', 'log_dinq_environment_variables']
except ImportError:
    __all__ = ['API_KEYS', 'load_environment_variables', 'get_env_var', 'log_dinq_environment_variables']
