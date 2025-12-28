"""
Scholar cache utility for DINQ project.
This module provides functions to cache and retrieve scholar information from the database.
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from src.utils.scholar_repository import scholar_repo, get_scholar_by_id, get_one_by_name,save_scholar_data,get_scholar_by_id_with_cache

# 配置日志（支持trace ID）
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger('scholar_cache')
except ImportError:
    # Fallback to regular logger if trace context is not available
    logger = logging.getLogger('scholar_cache')

def get_cached_scholar(scholar_id: str, max_age_days: int = 30, name:str = None) -> Optional[Dict[str, Any]]:
    """
    从缓存中获取学者信息，如果缓存不存在或已过期则返回None

    Args:
        scholar_id: Google Scholar ID
        max_age_days: 缓存最大有效期（天）

    Returns:
        学者信息字典或None（如果缓存不存在或已过期）
    """
    # 检查缓存是否有效

    if not scholar_repo.is_cache_valid(scholar_id, max_age_days, name=name):
        logger.info(f"Scholar {scholar_id} 缓存不存在或已过期")
        return None

    # 获取缓存数据
    if not scholar_id and name:
        scholar_data = get_one_by_name(name=name)
    else:
        scholar_data = get_scholar_by_id(scholar_id)
    if scholar_data:
        logger.info(f"从缓存获取到 Scholar {scholar_id} 的数据")
        return scholar_data

    return None

def get_cached_scholar_no_log(scholar_id: str, max_age_days: int = 30) -> Optional[Dict[str, Any]]:
    """
    从缓存中获取学者信息，如果缓存不存在或已过期则返回None

    Args:
        scholar_id: Google Scholar ID
        max_age_days: 缓存最大有效期（天）

    Returns:
        学者信息字典或None（如果缓存不存在或已过期）
    """

    # 获取缓存数据
    scholar_data = get_scholar_by_id_with_cache(scholar_id,max_age_days)
    return scholar_data

def cache_scholar_data(scholar_data: Dict[str, Any]) -> bool:
    """
    缓存学者信息到数据库

    Args:
        scholar_data: 包含学者信息的字典，必须包含scholar_id字段

    Returns:
        是否成功缓存
    """
    scholar_id = scholar_data.get('scholar_id')
    if not scholar_id:
        logger.error("缓存学者信息时缺少scholar_id")
        return False

    # 添加或更新时间戳
    scholar_data['last_updated'] = datetime.now()

    # 保存到数据库
    success = save_scholar_data(scholar_data)
    if success:
        logger.info(f"成功缓存 Scholar {scholar_id} 的数据")
    else:
        logger.error(f"缓存 Scholar {scholar_id} 的数据失败")

    return success

def clear_outdated_cache(max_age_days: int = 30, limit: int = 100) -> int:
    """
    清理过期的缓存数据

    Args:
        max_age_days: 缓存最大有效期（天）
        limit: 单次清理的最大记录数

    Returns:
        清理的记录数
    """
    outdated_records = scholar_repo.get_outdated_records(max_age_days, limit)
    count = 0

    for record in outdated_records:
        if scholar_repo.delete(record.id):
            count += 1

    if count > 0:
        logger.info(f"清理了 {count} 条过期的学者缓存数据")

    return count
