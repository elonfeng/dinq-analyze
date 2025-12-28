from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, DateTime, create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class BaseModel(Base):
    """数据库模型基类"""
    __abstract__ = True

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AnalysisResult(BaseModel):
    """分析结果存储模型"""
    __tablename__ = "analysis_result"

    result = Column(String, nullable=False)


def create_database_session(database_url: str = "sqlite:///analysis_result.db"):
    """创建数据库会话"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
