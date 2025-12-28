"""
Reports Handler API

This module handles requests for files in the reports directory.
"""

import os
from typing import Tuple, Optional
from flask import send_from_directory, abort


def get_reports_path() -> str:
    """
    Get the absolute path to the reports directory.
    
    Returns:
        Absolute path to the reports directory
    """
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 构建reports目录的绝对路径
    reports_path = os.path.join(project_root, 'reports')
    
    # 确保目录存在
    if not os.path.exists(reports_path):
        os.makedirs(reports_path, exist_ok=True)
    
    return reports_path


def serve_report_file(path: str) -> Tuple[any, int]:
    """
    Serve a file from the reports directory.
    
    Args:
        path: The path to the requested file, relative to the reports directory
        
    Returns:
        Flask response object and status code
    """
    reports_dir = get_reports_path()
    
    # 如果路径为空，返回404（报告目录不应该有默认页面）
    if not path:
        abort(404)  # Not Found
    
    # 确保路径不包含任何尝试访问父目录的部分（安全检查）
    if '..' in path:
        abort(403)  # Forbidden
    
    # 检查文件是否存在
    file_path = os.path.join(reports_dir, path)
    if not os.path.exists(file_path):
        # 如果是目录，尝试提供该目录下的index.html（如果存在）
        if os.path.isdir(file_path):
            index_path = os.path.join(path, 'index.html')
            if not os.path.exists(os.path.join(reports_dir, index_path)):
                abort(404)  # Not Found
            path = index_path
        else:
            abort(404)  # Not Found
    
    # 提供文件
    return send_from_directory(reports_dir, path), 200
