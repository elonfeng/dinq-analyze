"""
Scholar Database Cache

This module contains functions for caching scholar data in the database.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# 设置日志记录器（支持trace ID）
try:
    from server.utils.trace_context import get_trace_logger

    logger = get_trace_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# 导入数据库相关模块
try:
    from src.utils.scholar_cache import get_cached_scholar,get_cached_scholar_no_log, cache_scholar_data
    from src.utils.db_utils import create_tables

    # 避免在 import 时强制连外部 DB；如需自动建表，请显式打开开关。
    auto_create = os.getenv("DINQ_DB_AUTO_CREATE_TABLES", "false").lower() in ("1", "true", "yes", "on")
    if auto_create:
        try:
            create_tables()
        except Exception as e:  # noqa: BLE001
            logger.warning("自动建表失败（已忽略，缓存仍可尝试使用）: %s", e)

    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"数据库模块导入失败，缓存功能将不可用: {e}")
    DB_AVAILABLE = False

def get_scholar_from_cache(scholar_id: str, max_age_days: int = 3, name:str = None) -> Optional[Dict[str, Any]]:
    """
    从数据库缓存中获取学者数据

    Args:
        scholar_id: Google Scholar ID
        max_age_days: 缓存最大有效期（天）

    Returns:
        学者报告数据或None（如果缓存不存在或已过期）
    """

    try:
        # 从缓存获取数据
        cached_data = get_cached_scholar(scholar_id, max_age_days,name=name)
        if cached_data and cached_data.get('report_data'):
            logger.info(f"从缓存获取到 Scholar {scholar_id} 的数据")
            return cached_data['report_data']
    except Exception as e:
        logger.error(f"从缓存获取学者数据时出错: {e}")

    return None

def get_scholar_from_cache_no_log(scholar_id: str, max_age_days: int = 3) -> Optional[Dict[str, Any]]:
    """
    从数据库缓存中获取学者数据

    Args:
        scholar_id: Google Scholar ID
        max_age_days: 缓存最大有效期（天）

    Returns:
        学者报告数据或None（如果缓存不存在或已过期）
    """
    if not DB_AVAILABLE or not scholar_id:
        return None

    try:
        # 从缓存获取数据
        cached_data = get_cached_scholar_no_log(scholar_id, max_age_days)
        if cached_data and cached_data.get('report_data'):
            return cached_data['report_data']
    except Exception as e:
        logger.error(f"从缓存获取学者数据时出错: {e}")

    return None

def save_scholar_to_cache(scholar_data: Dict[str, Any], scholar_id: str) -> bool:
    """
    将学者数据保存到数据库缓存

    Args:
        scholar_data: 学者报告数据
        scholar_id: Google Scholar ID

    Returns:
        是否成功保存
    """
    if not DB_AVAILABLE or not scholar_id or not scholar_data:
        return False

    try:
        # 准备缓存数据
        researcher = scholar_data.get('researcher', {})

        cache_data = {
            'scholar_id': scholar_id,
            'name': researcher.get('name', ''),
            'affiliation': researcher.get('affiliation', ''),
            'research_fields': researcher.get('research_fields', []),
            'total_citations': researcher.get('total_citations', 0),
            'h_index': researcher.get('h_index', 0),
            'i10_index': researcher.get('i10_index', 0) if 'i10_index' in researcher else None,
            'report_data': scholar_data
        }

        # 保存到缓存
        success = cache_scholar_data(cache_data)
        if success:
            logger.info(f"成功缓存 Scholar {scholar_id} 的数据")
        else:
            logger.error(f"缓存 Scholar {scholar_id} 的数据失败")

        return success
    except Exception as e:
        logger.error(f"保存学者数据到缓存时出错: {e}")
        return False
