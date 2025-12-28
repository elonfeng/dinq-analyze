"""
Images Handler API

This module handles requests for files in the images directory.
"""

import os
from typing import Tuple, Optional
from flask import send_from_directory, abort


def get_images_path() -> str:
    """
    Get the absolute path to the images directory.
    
    Returns:
        Absolute path to the images directory
    """
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 构建images目录的绝对路径
    images_path = os.path.join(project_root, 'images')
    
    # 确保目录存在
    if not os.path.exists(images_path):
        os.makedirs(images_path, exist_ok=True)
    
    return images_path


def serve_image_file(path: str) -> Tuple[any, int]:
    """
    Serve a file from the images directory.
    
    Args:
        path: The path to the requested file, relative to the images directory
        
    Returns:
        Flask response object and status code
    """
    images_dir = get_images_path()
    
    # 如果路径为空，返回404（图片目录不应该有默认页面）
    if not path:
        abort(404)  # Not Found
    
    # 确保路径不包含任何尝试访问父目录的部分（安全检查）
    if '..' in path:
        abort(403)  # Forbidden
    
    # 检查文件是否存在
    file_path = os.path.join(images_dir, path)
    if not os.path.exists(file_path):
        # 如果是目录，返回404（不支持目录列表）
        if os.path.isdir(file_path):
            abort(404)  # Not Found
        else:
            abort(404)  # Not Found
    
    # 提供文件
    return send_from_directory(images_dir, path), 200
