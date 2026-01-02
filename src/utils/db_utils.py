"""
Database utility functions for DINQ project.
"""
import logging
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Type, TypeVar, Union, Generic
from contextlib import contextmanager

from sqlalchemy import create_engine, text, select, update, delete, func, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.pool import StaticPool

from src.models.db import Base, Scholar

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db_utils')

_DEFAULT_DB_URL = "sqlite:///./dinq.db"


def _get_jobs_db_url() -> str:
    """
    Resolve JOBS DB URL from env.

    优先级：
      1) DINQ_JOBS_DB_URL
      2) DINQ_DB_URL
      3) DATABASE_URL / DB_URL
      3) 代码内默认（仅本地 SQLite；不包含任何线上/密钥信息）
    """
    return (
        os.getenv("DINQ_JOBS_DB_URL")
        or os.getenv("DINQ_DB_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("DB_URL")
        or _DEFAULT_DB_URL
    )


def _get_cache_db_url() -> str:
    """
    Resolve CACHE DB URL from env.

    优先级：
      1) DINQ_CACHE_DB_URL
      2) DINQ_DB_URL
      3) DATABASE_URL / DB_URL
      4) 默认 SQLite（仅本地）

    说明：当未显式配置 cache DB 时，默认与 jobs DB 共用同一个 DB URL（向后兼容）。
    """

    return (
        os.getenv("DINQ_CACHE_DB_URL")
        or os.getenv("DINQ_DB_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("DB_URL")
        or _DEFAULT_DB_URL
    )


def _get_backup_db_url() -> str:
    """
    Resolve BACKUP DB URL from env.

    This DB is used ONLY for asynchronous replication of analysis caches (outbox pattern).
    It must NOT be on the online request critical path.

    Env:
      DINQ_BACKUP_DB_URL
    """

    return str(os.getenv("DINQ_BACKUP_DB_URL") or "").strip()


DB_URL = _get_jobs_db_url()
CACHE_DB_URL = _get_cache_db_url()
BACKUP_DB_URL = _get_backup_db_url()


def _create_engine(db_url: str, *, role: str):
    """
    Create SQLAlchemy engine with sane defaults for Postgres/SQLite.
    """
    url = (db_url or "").lower()

    # Common defaults
    role_key = str(role or "").strip().upper()
    echo = (os.getenv(f"DINQ_{role_key}_DB_ECHO") or os.getenv("DINQ_DB_ECHO") or "false").lower() in ("1", "true", "yes", "on")

    if url.startswith("sqlite"):
        # SQLite 主要用于离线/CI（不需要 pool settings）
        connect_args = {"check_same_thread": False}
        role_key = str(role or "").strip().upper()
        busy_timeout_ms = int(
            os.getenv(f"DINQ_{role_key}_SQLITE_BUSY_TIMEOUT_MS")
            or os.getenv("DINQ_SQLITE_BUSY_TIMEOUT_MS")
            or os.getenv("DINQ_SQLITE_CACHE_BUSY_TIMEOUT_MS")
            or "5000"
        )

        def _install_sqlite_pragmas(eng):
            @event.listens_for(eng, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
                try:
                    cur = dbapi_connection.cursor()
                    cur.execute("PRAGMA foreign_keys=ON;")
                    cur.execute("PRAGMA journal_mode=WAL;")
                    cur.execute("PRAGMA synchronous=NORMAL;")
                    cur.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)};")
                    cur.close()
                except Exception:
                    return

        if db_url.endswith(":memory:") or db_url.endswith(":///:memory:"):
            eng = create_engine(
                db_url,
                echo=echo,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
            _install_sqlite_pragmas(eng)
            return eng
        eng = create_engine(db_url, echo=echo, connect_args=connect_args)
        _install_sqlite_pragmas(eng)
        return eng

    # Postgres / MySQL
    pool_size = int(os.getenv(f"DINQ_{role_key}_DB_POOL_SIZE") or os.getenv("DINQ_DB_POOL_SIZE") or "10")
    max_overflow = int(os.getenv(f"DINQ_{role_key}_DB_MAX_OVERFLOW") or os.getenv("DINQ_DB_MAX_OVERFLOW") or "20")
    pool_timeout = int(os.getenv(f"DINQ_{role_key}_DB_POOL_TIMEOUT") or os.getenv("DINQ_DB_POOL_TIMEOUT") or "30")
    pool_recycle = int(os.getenv(f"DINQ_{role_key}_DB_POOL_RECYCLE") or os.getenv("DINQ_DB_POOL_RECYCLE") or "3600")

    connect_timeout = int(os.getenv(f"DINQ_{role_key}_DB_CONNECT_TIMEOUT") or os.getenv("DINQ_DB_CONNECT_TIMEOUT") or "30")
    application_name = os.getenv(f"DINQ_{role_key}_DB_APP_NAME") or os.getenv("DINQ_DB_APP_NAME") or "DINQ_App"
    connect_args = {"connect_timeout": connect_timeout}
    if url.startswith("postgresql"):
        connect_args["application_name"] = application_name

        # Optional: isolate this process into a specific schema (useful for benches/dev against a shared DB).
        # Example: DINQ_DB_SCHEMA=dinq_bench (we auto-append public) => search_path=dinq_bench,public
        raw_search_path = (
            os.getenv(f"DINQ_{role_key}_DB_SCHEMA")
            or os.getenv(f"DINQ_{role_key}_DB_SEARCH_PATH")
            or os.getenv("DINQ_DB_SCHEMA")
            or os.getenv("DINQ_DB_SEARCH_PATH")
        )
        if raw_search_path:
            parts = [p.strip() for p in str(raw_search_path).split(",") if p.strip()]
            if parts and "public" not in parts:
                parts.append("public")
            if parts:
                connect_args["options"] = f"-c search_path={','.join(parts)}"

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


# Two-engine topology:
# - jobs_engine: job/events/artifacts (often local SQLite for speed + multi-process sharing on one machine)
# - cache_engine: cross-job final_result cache (often remote Postgres as the single source of truth)
jobs_engine = _create_engine(DB_URL, role="jobs")
cache_engine = _create_engine(CACHE_DB_URL, role="cache")
backup_engine = _create_engine(BACKUP_DB_URL, role="backup") if BACKUP_DB_URL else None

# Backward-compatible alias: most of the codebase expects `engine` to be the primary DB.
engine = jobs_engine


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
JobsSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=jobs_engine, expire_on_commit=False)
CacheSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cache_engine, expire_on_commit=False)
BackupSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=backup_engine, expire_on_commit=False) if backup_engine is not None else None
# Backward-compatible alias
SessionLocal = JobsSessionLocal

# 定义模型类型变量，用于泛型
T = TypeVar('T')

@contextmanager
def get_jobs_db_session():
    """获取 jobs DB 会话（job/events/artifacts 等运行态数据）。"""
    session = JobsSessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库会话错误: {e}")
        raise
    finally:
        session.close()


@contextmanager
def get_cache_db_session():
    """获取 cache DB 会话（final_result 等跨 job 缓存）。"""
    session = CacheSessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库会话错误: {e}")
        raise
    finally:
        session.close()


@contextmanager
def get_backup_db_session():
    """获取 backup DB 会话（只用于异步备份/冷启动读回，不应该阻塞在线请求）。"""
    if backup_engine is None or BackupSessionLocal is None:
        raise ValueError("backup DB is not configured (set DINQ_BACKUP_DB_URL)")
    session = BackupSessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库会话错误(backup): {e}")
        raise
    finally:
        session.close()


@contextmanager
def get_db_session():
    """
    Backward-compatible alias for jobs DB session.

    Most legacy repos in dinq use a single DB. In the new topology, jobs DB is the default.
    """

    with get_jobs_db_session() as session:
        yield session


def _is_same_db() -> bool:
    return str(DB_URL or "") == str(CACHE_DB_URL or "")


_CACHE_TABLE_NAMES = {
    "analysis_subjects",
    "analysis_artifact_cache",
    "analysis_runs",
    "analysis_resource_versions",
    "analysis_backup_outbox",
}


def _tables_except_cache():
    return [t for name, t in Base.metadata.tables.items() if name not in _CACHE_TABLE_NAMES]


def _cache_tables():
    return [t for name, t in Base.metadata.tables.items() if name in _CACHE_TABLE_NAMES]

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

        # If cache DB is not configured, keep legacy behavior: one DB contains everything.
        if _is_same_db():
            target_engine = jobs_engine
            raw_schema = (
                os.getenv("DINQ_JOBS_DB_SCHEMA")
                or os.getenv("DINQ_JOBS_DB_SEARCH_PATH")
                or os.getenv("DINQ_DB_SCHEMA")
                or os.getenv("DINQ_DB_SEARCH_PATH")
            )
            non_public_schemas: list[str] = []
            if target_engine.dialect.name == "postgresql" and raw_schema:
                non_public_schemas = [p.strip() for p in str(raw_schema).split(",") if p.strip() and p.strip() != "public"]
                for schema in non_public_schemas:
                    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
                        logger.warning("Skipping invalid schema name in DINQ_DB_SCHEMA: %s", schema)
                        continue
                    with target_engine.begin() as conn:
                        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

            if target_engine.dialect.name == "postgresql" and non_public_schemas:
                orig_default_schema = getattr(target_engine.dialect, "default_schema_name", None)
                try:
                    target_engine.dialect.default_schema_name = non_public_schemas[0]
                    Base.metadata.create_all(bind=target_engine)
                finally:
                    try:
                        target_engine.dialect.default_schema_name = orig_default_schema
                    except Exception:  # noqa: BLE001
                        pass
            else:
                Base.metadata.create_all(bind=target_engine)
            logger.info("数据库表创建成功")
            return True

        # Two-DB topology: split jobs vs cache tables.
        # - jobs_engine gets everything EXCEPT analysis cache tables
        # - cache_engine gets only analysis cache tables
        jobs_raw_schema = (
            os.getenv("DINQ_JOBS_DB_SCHEMA")
            or os.getenv("DINQ_JOBS_DB_SEARCH_PATH")
            or os.getenv("DINQ_DB_SCHEMA")
            or os.getenv("DINQ_DB_SEARCH_PATH")
        )
        jobs_non_public_schemas: list[str] = []
        if jobs_engine.dialect.name == "postgresql" and jobs_raw_schema:
            jobs_non_public_schemas = [p.strip() for p in str(jobs_raw_schema).split(",") if p.strip() and p.strip() != "public"]
            for schema in jobs_non_public_schemas:
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
                    logger.warning("Skipping invalid schema name in DINQ_JOBS_DB_SCHEMA: %s", schema)
                    continue
                with jobs_engine.begin() as conn:
                    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

        if jobs_engine.dialect.name == "postgresql" and jobs_non_public_schemas:
            orig_default_schema = getattr(jobs_engine.dialect, "default_schema_name", None)
            try:
                jobs_engine.dialect.default_schema_name = jobs_non_public_schemas[0]
                Base.metadata.create_all(bind=jobs_engine, tables=_tables_except_cache())
            finally:
                try:
                    jobs_engine.dialect.default_schema_name = orig_default_schema
                except Exception:  # noqa: BLE001
                    pass
        else:
            Base.metadata.create_all(bind=jobs_engine, tables=_tables_except_cache())

        raw_schema = (
            os.getenv("DINQ_CACHE_DB_SCHEMA")
            or os.getenv("DINQ_CACHE_DB_SEARCH_PATH")
            or os.getenv("DINQ_DB_SCHEMA")
            or os.getenv("DINQ_DB_SEARCH_PATH")
        )
        non_public_schemas = []
        if cache_engine.dialect.name == "postgresql" and raw_schema:
            non_public_schemas = [p.strip() for p in str(raw_schema).split(",") if p.strip() and p.strip() != "public"]
            for schema in non_public_schemas:
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
                    logger.warning("Skipping invalid schema name in DINQ_CACHE_DB_SCHEMA: %s", schema)
                    continue
                with cache_engine.begin() as conn:
                    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

        if cache_engine.dialect.name == "postgresql" and non_public_schemas:
            orig_default_schema = getattr(cache_engine.dialect, "default_schema_name", None)
            try:
                cache_engine.dialect.default_schema_name = non_public_schemas[0]
                Base.metadata.create_all(bind=cache_engine, tables=_cache_tables())
            finally:
                try:
                    cache_engine.dialect.default_schema_name = orig_default_schema
                except Exception:  # noqa: BLE001
                    pass
        else:
            Base.metadata.create_all(bind=cache_engine, tables=_cache_tables())
        logger.info("数据库表创建成功")
        return True
    except SQLAlchemyError as e:
        logger.error(f"创建数据库表时出错: {e}")
        return False


def backup_db_enabled() -> bool:
    """Whether a remote backup DB is configured."""
    return bool(str(BACKUP_DB_URL or "").strip()) and backup_engine is not None


def ensure_sqlite_tables_created() -> None:
    """
    Best-effort: auto-create tables when using local SQLite engines.

    Rationale:
    - Local-first deployments frequently rely on SQLite files that may not exist yet.
    - Creating tables is safe and fast for SQLite, and avoids manual bootstrap steps.
    - This function NEVER touches non-SQLite engines (e.g. Postgres).
    """

    # Ensure all models are imported so Base.metadata is complete.
    try:
        import src.models.user_verification  # noqa: F401
        import src.models.job_board  # noqa: F401
        import src.models.user_interactions  # noqa: F401
    except Exception:  # noqa: BLE001
        pass

    try:
        if jobs_engine.dialect.name == "sqlite":
            Base.metadata.create_all(bind=jobs_engine, tables=_tables_except_cache())
    except Exception:
        pass

    try:
        if cache_engine.dialect.name == "sqlite":
            Base.metadata.create_all(bind=cache_engine, tables=_cache_tables())
    except Exception:
        pass


# Auto-create tables for local SQLite engines (best-effort, non-blocking).
try:
    ensure_sqlite_tables_created()
except Exception:
    pass


def drop_tables():
    """删除所有表（谨慎使用）"""
    try:
        if _is_same_db():
            Base.metadata.drop_all(bind=engine)
        else:
            Base.metadata.drop_all(bind=jobs_engine, tables=_tables_except_cache())
            Base.metadata.drop_all(bind=cache_engine, tables=_cache_tables())
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
