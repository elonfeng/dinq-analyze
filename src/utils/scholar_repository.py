"""
Scholar repository for database operations.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from src.models.db import Scholar, Base
from src.utils.db_utils import DatabaseRepository, get_db_session

# 配置日志
logger = logging.getLogger('scholar_repository')

class ScholarRepository(DatabaseRepository[Scholar]):
    """Scholar数据库仓库，提供特定于Scholar模型的操作"""

    def __init__(self):
        super().__init__(Scholar)

    def get_by_scholar_id(self, scholar_id: str) -> Optional[Scholar]:
        """通过Google Scholar ID获取记录"""
        try:
            with get_db_session() as session:
                return session.query(Scholar).filter(Scholar.scholar_id == scholar_id).first()
        except SQLAlchemyError as e:
            logger.error(f"通过Scholar ID获取记录时出错: {e}")
            return None

    def get_by_name(self, name: str, limit: int = 10) -> List[Scholar]:
        """通过姓名模糊查询获取记录"""
        try:
            with get_db_session() as session:
                return session.query(Scholar).filter(Scholar.name.like(f"%{name}%")).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"通过姓名获取记录时出错: {e}")
            return []
        
    def is_cache_valid(self, scholar_id: str, max_age_days: int = 30, name: str = None) -> bool:
        """检查缓存是否有效（未过期）"""
        # 在会话中执行所有操作，避免分离实例错误
        try:
            with get_db_session() as session:
                if not scholar_id and name:
                    scholar = session.query(Scholar).filter(Scholar.name == name).first()
                else:
                    scholar = session.query(Scholar).filter(Scholar.scholar_id == scholar_id).first()
                if not scholar or not scholar.last_updated:
                    return False

                # 计算缓存是否过期
                max_age = timedelta(days=max_age_days)
                now = datetime.now()

                return (now - scholar.last_updated) < max_age
        except Exception as e:
            logger.error(f"检查缓存有效性时出错: {e}")
            return False

    def update_by_scholar_id(self, scholar_id: str, data: Dict[str, Any]) -> bool:
        """通过Google Scholar ID更新记录"""
        try:
            with get_db_session() as session:
                result = session.query(Scholar).filter(Scholar.scholar_id == scholar_id).update(data)
                return result > 0
        except SQLAlchemyError as e:
            logger.error(f"通过Scholar ID更新记录时出错: {e}")
            return False

    def delete_by_scholar_id(self, scholar_id: str) -> bool:
        """通过Google Scholar ID删除记录"""
        try:
            with get_db_session() as session:
                result = session.query(Scholar).filter(Scholar.scholar_id == scholar_id).delete()
                return result > 0
        except SQLAlchemyError as e:
            logger.error(f"通过Scholar ID删除记录时出错: {e}")
            return False

    def get_outdated_records(self, max_age_days: int = 30, limit: int = 100) -> List[Scholar]:
        """获取过期的记录，用于定时更新"""
        try:
            with get_db_session() as session:
                cutoff_date = datetime.now() - timedelta(days=max_age_days)
                return session.query(Scholar).filter(
                    Scholar.last_updated < cutoff_date
                ).order_by(Scholar.last_updated.asc()).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"获取过期记录时出错: {e}")
            return []

# 创建全局实例
scholar_repo = ScholarRepository()

# 为了兼容性提供函数接口
def get_scholar_by_id(scholar_id: str) -> Optional[Dict[str, Any]]:
    """通过Google Scholar ID获取学者信息"""
    try:
        with get_db_session() as session:
            scholar = session.query(Scholar).filter(Scholar.scholar_id == scholar_id).first()
            if scholar:
                return {
                    'id': scholar.id,
                    'scholar_id': scholar.scholar_id,
                    'name': scholar.name,
                    'affiliation': scholar.affiliation,
                    'email': scholar.email,
                    'research_fields': scholar.research_fields,
                    'total_citations': scholar.total_citations,
                    'h_index': scholar.h_index,
                    'i10_index': scholar.i10_index,
                    'report_data': scholar.report_data,
                    'last_updated': scholar.last_updated.isoformat() if scholar.last_updated else None
                }
    except Exception as e:
        logger.error(f"获取学者信息时出错: {e}")
    return None


def get_one_by_name(name: str) -> List[Scholar]:
    """通过姓名查询获取记录"""
    try:
        with get_db_session() as session:
            scholar = session.query(Scholar).filter(Scholar.name == name).first()
            if scholar:
                return {
                    'id': scholar.id,
                    'scholar_id': scholar.scholar_id,
                    'name': scholar.name,
                    'affiliation': scholar.affiliation,
                    'email': scholar.email,
                    'research_fields': scholar.research_fields,
                    'total_citations': scholar.total_citations,
                    'h_index': scholar.h_index,
                    'i10_index': scholar.i10_index,
                    'report_data': scholar.report_data,
                    'last_updated': scholar.last_updated.isoformat() if scholar.last_updated else None
                }
    except SQLAlchemyError as e:
        logger.error(f"通过姓名获取记录时出错: {e}")
        return None
        
def get_scholar_by_id_with_cache(scholar_id: str, max_age_days: int = 30) -> Optional[Dict[str, Any]]:
    """通过Google Scholar ID获取学者信息"""
    try:
        with get_db_session() as session:
            scholar = session.query(Scholar).filter(Scholar.scholar_id == scholar_id).first()
            if not scholar or not scholar.last_updated:
                return None
   
            max_age = timedelta(days=max_age_days)
            now = datetime.now()

            flag =  (now - scholar.last_updated) < max_age
            if not flag:
                return None
            if scholar:
                return {
                    'id': scholar.id,
                    'scholar_id': scholar.scholar_id,
                    'name': scholar.name,
                    'affiliation': scholar.affiliation,
                    'email': scholar.email,
                    'research_fields': scholar.research_fields,
                    'total_citations': scholar.total_citations,
                    'h_index': scholar.h_index,
                    'i10_index': scholar.i10_index,
                    'report_data': scholar.report_data,
                    'last_updated': scholar.last_updated.isoformat() if scholar.last_updated else None
                }
    except Exception as e:
        logger.error(f"获取学者信息时出错: {e}")
    return None

def get_scholar_name(scholar_id: str) -> Optional[str]:
    """通过Google Scholar ID获取学者信息"""

    with get_db_session() as session:
        scholar_name = session.query(Scholar.name).filter(Scholar.scholar_id == scholar_id).first()
        if not scholar_name :
            return None
        return scholar_name.name

def save_scholar_data(data: Dict[str, Any]) -> bool:
    """保存学者信息"""
    scholar_id = data.get('scholar_id')
    if not scholar_id:
        logger.error("保存学者信息时缺少scholar_id")
        return False

    # 检查是否已存在
    existing = scholar_repo.get_by_scholar_id(scholar_id)
    if existing:
        # 更新现有记录
        return scholar_repo.update_by_scholar_id(scholar_id, data)
    else:
        # 创建新记录
        return scholar_repo.create(data) is not None

def update_scholar_data(scholar_id: str, data: Dict[str, Any]) -> bool:
    """更新学者信息"""
    return scholar_repo.update_by_scholar_id(scholar_id, data)

def delete_scholar_data(scholar_id: str) -> bool:
    """删除学者信息"""
    return scholar_repo.delete_by_scholar_id(scholar_id)
