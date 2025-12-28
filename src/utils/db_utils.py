"""
Database utility functions for DINQ project.
"""
import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Type, TypeVar, Union, Generic
from contextlib import contextmanager

from sqlalchemy import create_engine, text, select, update, delete, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.pool import StaticPool

from src.models.db import Base, Scholar

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db_utils')

_DEFAULT_DB_URL = "sqlite:///./dinq.db"


def _get_db_url() -> str:
    """
    Resolve DB URL from env, with a backward-compatible Supabase fallback.

    优先级：
      1) DINQ_DB_URL
      2) DATABASE_URL / DB_URL
      3) 代码内默认（仅本地 SQLite；不包含任何线上/密钥信息）
    """
    return (
        os.getenv("DINQ_DB_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("DB_URL")
        or _DEFAULT_DB_URL
    )


DB_URL = _get_db_url()


def _create_engine(db_url: str):
    """
    Create SQLAlchemy engine with sane defaults for Postgres/SQLite.
    """
    url = (db_url or "").lower()

    # Common defaults
    echo = os.getenv("DINQ_DB_ECHO", "false").lower() in ("1", "true", "yes", "on")

    if url.startswith("sqlite"):
        # SQLite 主要用于离线/CI（不需要 pool settings）
        connect_args = {"check_same_thread": False}
        if db_url.endswith(":memory:") or db_url.endswith(":///:memory:"):
            return create_engine(
                db_url,
                echo=echo,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        return create_engine(db_url, echo=echo, connect_args=connect_args)

    # Postgres / MySQL
    pool_size = int(os.getenv("DINQ_DB_POOL_SIZE", "10"))
    max_overflow = int(os.getenv("DINQ_DB_MAX_OVERFLOW", "20"))
    pool_timeout = int(os.getenv("DINQ_DB_POOL_TIMEOUT", "30"))
    pool_recycle = int(os.getenv("DINQ_DB_POOL_RECYCLE", "3600"))

    connect_timeout = int(os.getenv("DINQ_DB_CONNECT_TIMEOUT", "30"))
    application_name = os.getenv("DINQ_DB_APP_NAME", "DINQ_App")
    connect_args = {"connect_timeout": connect_timeout}
    if url.startswith("postgresql"):
        connect_args["application_name"] = application_name

    return create_engine(
        db_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


engine = _create_engine(DB_URL)


# # 数据库连接配置
# DB_CONFIG = {
#     'host': '157.230.67.105',  # 可以使用IP地址或域名
#     'user': 'devuser',
#     'password': 'devpassword',
#     'database': 'devfun',
#     'port': 3306,
#     'allow_local_infile': True,  # 允许加载本地文件
#     'use_pure': True,  # 使用纯Python实现，提高兼容性
#     'auth_plugin': 'mysql_native_password'  # 使用原生密码认证
# }

# # 创建数据库连接URL
# DB_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

# # 创建SQLAlchemy引擎
# engine = create_engine(
#     DB_URL, 
#     echo=False,  # 设置为True可以查看SQL语句
#     pool_recycle=3600,  # 连接回收时间
#     pool_pre_ping=True  # 自动检测连接是否有效
# )

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# 定义模型类型变量，用于泛型
T = TypeVar('T')

@contextmanager
def get_db_session():
    """获取数据库会话的上下文管理器"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库会话错误: {e}")
        raise
    finally:
        session.close()

def create_tables():
    """创建所有表"""
    try:
        # 确保所有模型已 import，才能被 Base.metadata 收集到并创建表结构。
        try:
            import src.models.user_verification  # noqa: F401
            import src.models.job_board  # noqa: F401
            import src.models.user_interactions  # noqa: F401
        except Exception:  # noqa: BLE001
            # Best effort：即使这里失败，也尽量创建已注册的表，避免阻塞启动/测试
            pass

        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建成功")
        return True
    except SQLAlchemyError as e:
        logger.error(f"创建数据库表时出错: {e}")
        return False

def drop_tables():
    """删除所有表（谨慎使用）"""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("数据库表删除成功")
        return True
    except SQLAlchemyError as e:
        logger.error(f"删除数据库表时出错: {e}")
        return False

class DatabaseRepository(Generic[T]):
    """通用数据库仓库，提供基本的CRUD操作"""

    def __init__(self, model_class: Type[T]):
        self.model_class = model_class

    def create(self, obj_data: Dict[str, Any]) -> Optional[T]:
        """创建记录"""
        try:
            with get_db_session() as session:
                obj = self.model_class(**obj_data)
                session.add(obj)
                session.flush()  # 刷新以获取ID
                session.refresh(obj)
                return obj
        except SQLAlchemyError as e:
            logger.error(f"创建{self.model_class.__name__}记录时出错: {e}")
            return None

    def get_by_id(self, id: int) -> Optional[T]:
        """通过ID获取记录"""
        try:
            with get_db_session() as session:
                return session.query(self.model_class).filter(self.model_class.id == id).first()
        except SQLAlchemyError as e:
            logger.error(f"通过ID获取{self.model_class.__name__}记录时出错: {e}")
            return None

    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """获取所有记录"""
        try:
            with get_db_session() as session:
                return session.query(self.model_class).order_by(self.model_class.id.desc()).limit(limit).offset(offset).all()
        except SQLAlchemyError as e:
            logger.error(f"获取所有{self.model_class.__name__}记录时出错: {e}")
            return []

    def update(self, id: int, obj_data: Dict[str, Any]) -> bool:
        """更新记录"""
        try:
            with get_db_session() as session:
                result = session.query(self.model_class).filter(self.model_class.id == id).update(obj_data)
                return result > 0
        except SQLAlchemyError as e:
            logger.error(f"更新{self.model_class.__name__}记录时出错: {e}")
            return False

    def delete(self, id: int) -> bool:
        """删除记录"""
        try:
            with get_db_session() as session:
                result = session.query(self.model_class).filter(self.model_class.id == id).delete()
                return result > 0
        except SQLAlchemyError as e:
            logger.error(f"删除{self.model_class.__name__}记录时出错: {e}")
            return False

    def count(self) -> int:
        """获取记录总数"""
        try:
            with get_db_session() as session:
                return session.query(func.count(self.model_class.id)).scalar()
        except SQLAlchemyError as e:
            logger.error(f"获取{self.model_class.__name__}记录总数时出错: {e}")
            return 0
