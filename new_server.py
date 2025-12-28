#!/usr/bin/env python3
"""
Scholar Demo Server

This script starts the Scholar Demo server, which provides:
1. Streaming API for researcher data
2. Static file serving for Next.js build output
"""

import os
import sys
import argparse
import logging

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import the server package
from server.app import run_server


def main():
    """Main entry point for the server."""
    # Import logging configuration
    from server.utils.logging_config import setup_logging

    # Configure logging
    logger = setup_logging()
    logger = logging.getLogger(__name__)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Start the Scholar Demo server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5001, help='Port to listen on')
    parser.add_argument('--static-dir', help='Directory containing static files (Next.js build output)')

    args = parser.parse_args()

    # Determine the static directory
    static_dir = args.static_dir
    if not static_dir:
        static_dir = os.path.join(project_root, 'frontend', 'out')

    # Check if the static directory exists
    if not os.path.exists(static_dir):
        logger.warning(f"Static directory not found at {static_dir}")
        logger.warning("The server will still start, but static files will not be served correctly")

    # Start the server
    try:
        run_server(args.host, args.port, static_dir)
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
