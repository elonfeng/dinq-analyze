"""
Scholar repository for database operations.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from src.models.db import WebCache, Base
from src.utils.db_utils import DatabaseRepository, get_db_session

# 配置日志
logger = logging.getLogger('web_cache_repository')

class WebCacheRepository(DatabaseRepository[WebCache]):
    """分析结果页缓存仓库"""

    def __init__(self):
        super().__init__(WebCache)

    def get_by_type_uuid(self, type:str, uuid: str) -> Optional[WebCache]:
        """通过Google Scholar ID获取记录"""
        try:
            with get_db_session() as session:
                query = session.query(WebCache)
                if type:
                    query = query.filter(WebCache.type == type)

                if uuid:
                    query = query.filter(WebCache.uuid == uuid)
                
                cache = query.first()    
                result ={
                        "id": cache.id,
                        "type": cache.type,
                        "content": cache.content,
                        "uuid": cache.uuid,
                        "created_at": cache.created_at.isoformat() if cache.created_at else None,
                        "updated_at": cache.updated_at.isoformat() if cache.updated_at else None
                    }
                
                return result
        except SQLAlchemyError as e:
            logger.error(f"通过uuid和type获取记录时出错: {e}")
            return None


    def update(self, type:str, uuid: str, data: Dict[str, Any]) -> bool:
        """通过Google Scholar ID更新记录"""
        try:
            with get_db_session() as session:
                result = session.query(WebCache).filter(WebCache.uuid == uuid, WebCache.type == type).update(data)
                return result > 0
        except SQLAlchemyError as e:
            logger.error(f"通过uuid和type更新记录时出错: {e}")
            return False

    def add(self, type: str, uuid: str, content: str) -> Dict[str, Any]:

        if not type or not uuid:
            return {"success": False, "error": "type, uuid are required"}

        try:
            with get_db_session() as session:
                
                cache = WebCache(
                    type=type,
                    uuid=uuid,
                    content=content
                )
                session.add(cache)
                # Commit changes
                session.commit()

                result ={
                        "id": cache.id,
                        "type": cache.type,
                        "content": cache.content,
                        "uuid": cache.uuid,
                        "created_at": cache.created_at.isoformat() if cache.created_at else None,
                        "updated_at": cache.updated_at.isoformat() if cache.updated_at else None
                    }
                
                return result

        except SQLAlchemyError as e:
            logger.error(f"Database error adding to waiting list: {str(e)}")
            return {"success": False, "error": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error adding to waiting list: {str(e)}")
            return {"success": False, "error": f"Error: {str(e)}"}


# 创建全局实例
web_cachr_repo = WebCacheRepository()

