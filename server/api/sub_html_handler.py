"""
Sub HTML Handler API

This module handles requests for sub_html directory files.
"""

import os
from typing import Tuple, Optional
from flask import send_from_directory, abort


def get_sub_html_path() -> str:
    """
    Get the absolute path to the sub_html directory.
    
    Returns:
        Absolute path to the sub_html directory
    """
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 构建sub_html目录的绝对路径
    sub_html_path = os.path.join(project_root, 'sub_html')
    
    # 确保目录存在
    if not os.path.exists(sub_html_path):
        os.makedirs(sub_html_path, exist_ok=True)
    
    return sub_html_path


def serve_sub_html_file(path: str) -> Tuple[any, int]:
    """
    Serve a file from the sub_html directory.
    
    Args:
        path: The path to the requested file, relative to the sub_html directory
        
    Returns:
        Flask response object and status code
    """
    sub_html_dir = get_sub_html_path()
    
    # 如果路径为空，尝试提供index.html
    if not path:
        path = 'index.html'
    
    # 确保路径不包含任何尝试访问父目录的部分（安全检查）
    if '..' in path:
        abort(403)  # Forbidden
    
    # 检查文件是否存在
    file_path = os.path.join(sub_html_dir, path)
    if not os.path.exists(file_path):
        # 如果是目录，尝试提供该目录下的index.html
        if os.path.isdir(file_path):
            path = os.path.join(path, 'index.html')
            if not os.path.exists(os.path.join(sub_html_dir, path)):
                abort(404)  # Not Found
        else:
            abort(404)  # Not Found
    
    # 提供文件
    return send_from_directory(sub_html_dir, path), 200
