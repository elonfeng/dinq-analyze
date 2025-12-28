"""
Job Board API Integration

This module provides functions to integrate the job board API into the main application.
"""

import logging
from flask import Flask

from server.api.job_board import job_board_bp

# 配置日志
logger = logging.getLogger('server.api.job_board.integration')

def register_job_board_api(app: Flask) -> None:
    """
    Register the job board API blueprint with the Flask application.
    
    Args:
        app: Flask application
    """
    try:
        # 注册蓝图
        app.register_blueprint(job_board_bp)
        logger.info("Job Board API registered successfully")
    except Exception as e:
        logger.error(f"Failed to register Job Board API: {e}")
        raise
