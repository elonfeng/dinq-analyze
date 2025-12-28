"""
数据库配置管理器

支持多种数据库连接方式：
1. Supabase PostgreSQL (主要)
2. 本地PostgreSQL (备用)
3. MySQL (兼容)
4. SQLite (开发/测试)
"""

import os
import logging
from typing import Dict, Any, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db_config')

# 创建Base类
Base = declarative_base()

class DatabaseConfig:
    """数据库配置管理器"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.current_config = None
        
    def get_supabase_config(self) -> Dict[str, Any]:
        """获取Supabase PostgreSQL配置"""
        # NOTE: Do NOT hardcode any real production DB URLs or passwords in the repo.
        # Prefer injecting via env (DINQ_DB_URL / DATABASE_URL / DB_URL).
        db_url = os.getenv("DINQ_DB_URL") or os.getenv("DATABASE_URL") or os.getenv("DB_URL") or ""
        return {
            'name': 'Supabase PostgreSQL',
            'url': db_url or "postgresql+psycopg2://postgres:<PASSWORD>@<HOST>:5432/postgres?sslmode=require",
            'connect_args': {
                "sslmode": "require",
                "connect_timeout": 30,
                "application_name": "DINQ_App"
            },
            'pool_settings': {
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True
            }
        }
    
    def get_local_postgresql_config(self) -> Dict[str, Any]:
        """获取本地PostgreSQL配置"""
        host = os.getenv('LOCAL_PG_HOST', 'localhost')
        port = os.getenv('LOCAL_PG_PORT', '5432')
        user = os.getenv('LOCAL_PG_USER', 'postgres')
        password = os.getenv('LOCAL_PG_PASSWORD', 'password')
        database = os.getenv('LOCAL_PG_DATABASE', 'dinq')
        
        return {
            'name': 'Local PostgreSQL',
            'url': f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}",
            'connect_args': {
                "connect_timeout": 10,
                "application_name": "DINQ_App"
            },
            'pool_settings': {
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 20,
                'pool_recycle': 1800,
                'pool_pre_ping': True
            }
        }
    
    def get_mysql_config(self) -> Dict[str, Any]:
        """获取MySQL配置（兼容旧版本）"""
        host = os.getenv('MYSQL_HOST', '157.230.67.105')
        port = os.getenv('MYSQL_PORT', '3306')
        user = os.getenv('MYSQL_USER', 'devuser')
        password = os.getenv('MYSQL_PASSWORD', 'devpassword')
        database = os.getenv('MYSQL_DATABASE', 'devfun')
        
        return {
            'name': 'MySQL',
            'url': f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}",
            'connect_args': {
                'connect_timeout': 30,
                'charset': 'utf8mb4'
            },
            'pool_settings': {
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 20,
                'pool_recycle': 1800,
                'pool_pre_ping': True
            }
        }
    
    def get_sqlite_config(self) -> Dict[str, Any]:
        """获取SQLite配置（开发/测试）"""
        db_path = os.getenv('SQLITE_PATH', 'dinq.db')
        
        return {
            'name': 'SQLite',
            'url': f"sqlite:///{db_path}",
            'connect_args': {
                'check_same_thread': False,
                'timeout': 20
            },
            'pool_settings': {
                'pool_pre_ping': True
            }
        }
    
    def test_connection(self, config: Dict[str, Any]) -> bool:
        """测试数据库连接"""
        try:
            logger.info(f"测试连接到 {config['name']}...")
            
            # 创建临时引擎
            engine_args = {
                'echo': False,
                **config['pool_settings']
            }
            
            if 'connect_args' in config:
                engine_args['connect_args'] = config['connect_args']
            
            test_engine = create_engine(config['url'], **engine_args)
            
            # 测试连接
            with test_engine.connect() as connection:
                if 'postgresql' in config['url']:
                    from sqlalchemy import text
                    result = connection.execute(text("SELECT version();"))
                    version = result.fetchone()[0]
                    logger.info(f"PostgreSQL版本: {version}")
                elif 'mysql' in config['url']:
                    from sqlalchemy import text
                    result = connection.execute(text("SELECT VERSION();"))
                    version = result.fetchone()[0]
                    logger.info(f"MySQL版本: {version}")
                elif 'sqlite' in config['url']:
                    from sqlalchemy import text
                    result = connection.execute(text("SELECT sqlite_version();"))
                    version = result.fetchone()[0]
                    logger.info(f"SQLite版本: {version}")
                
                logger.info(f"✅ {config['name']} 连接成功")
                test_engine.dispose()
                return True
                
        except Exception as e:
            logger.warning(f"❌ {config['name']} 连接失败: {e}")
            return False
    
    def initialize_database(self, preferred_db: str = 'auto') -> bool:
        """
        初始化数据库连接
        
        Args:
            preferred_db: 首选数据库类型 ('supabase', 'local_pg', 'mysql', 'sqlite', 'auto')
        
        Returns:
            bool: 是否成功初始化
        """
        configs = []
        
        if preferred_db == 'auto':
            # 自动选择：按优先级尝试
            configs = [
                self.get_supabase_config(),
                self.get_local_postgresql_config(),
                self.get_mysql_config(),
                self.get_sqlite_config()
            ]
        elif preferred_db == 'supabase':
            configs = [self.get_supabase_config()]
        elif preferred_db == 'local_pg':
            configs = [self.get_local_postgresql_config()]
        elif preferred_db == 'mysql':
            configs = [self.get_mysql_config()]
        elif preferred_db == 'sqlite':
            configs = [self.get_sqlite_config()]
        else:
            logger.error(f"未知的数据库类型: {preferred_db}")
            return False
        
        # 尝试连接每个配置
        for config in configs:
            if self.test_connection(config):
                # 连接成功，创建引擎和会话
                try:
                    engine_args = {
                        'echo': False,
                        **config['pool_settings']
                    }
                    
                    if 'connect_args' in config:
                        engine_args['connect_args'] = config['connect_args']
                    
                    self.engine = create_engine(config['url'], **engine_args)
                    self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
                    self.current_config = config
                    
                    logger.info(f"🎉 数据库初始化成功，使用: {config['name']}")
                    
                    # 创建表
                    self.create_tables()
                    
                    return True
                    
                except Exception as e:
                    logger.error(f"创建引擎失败: {e}")
                    continue
        
        logger.error("❌ 所有数据库连接都失败了")
        return False
    
    def create_tables(self):
        """创建数据库表"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ 数据库表创建/验证成功")
        except Exception as e:
            logger.error(f"创建数据库表失败: {e}")
            raise
    
    def get_session(self):
        """获取数据库会话"""
        if self.SessionLocal is None:
            raise RuntimeError("数据库未初始化，请先调用 initialize_database()")
        return self.SessionLocal()
    
    def get_engine(self):
        """获取数据库引擎"""
        if self.engine is None:
            raise RuntimeError("数据库未初始化，请先调用 initialize_database()")
        return self.engine
    
    def get_current_config_info(self) -> Optional[Dict[str, Any]]:
        """获取当前数据库配置信息"""
        return self.current_config

# 创建全局数据库配置实例
db_config = DatabaseConfig()

# 兼容性函数，保持与原有代码的兼容性
def get_engine():
    """获取数据库引擎（兼容性函数）"""
    return db_config.get_engine()

def get_session():
    """获取数据库会话（兼容性函数）"""
    return db_config.get_session()

# 导出常用对象
engine = None  # 将在初始化后设置
SessionLocal = None  # 将在初始化后设置

def initialize_database_connection(preferred_db: str = 'auto') -> bool:
    """
    初始化数据库连接的便捷函数
    
    Args:
        preferred_db: 首选数据库类型
    
    Returns:
        bool: 是否成功初始化
    """
    global engine, SessionLocal
    
    success = db_config.initialize_database(preferred_db)
    if success:
        engine = db_config.get_engine()
        SessionLocal = db_config.get_session
    
    return success
