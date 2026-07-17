# backend/database.py
"""
[What] 数据库连接配置
[Why] 统一管理数据库会话和引擎
[How] 使用SQLAlchemy的create_engine和sessionmaker，延迟初始化
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


# [What] 创建模型基类
# [Why] 所有模型需要继承同一个基类
# [How] 使用SQLAlchemy 2.0的DeclarativeBase
class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _get_engine():
    """
    [What] 获取数据库引擎（延迟初始化）
    [Why] 避免模块导入时就连接数据库
    [How] 首次调用时创建引擎
    """
    global _engine
    if _engine is None:
        url = settings.DATABASE_URL
        kwargs = {"echo": settings.DEBUG}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20
            kwargs["pool_pre_ping"] = True
            kwargs["pool_recycle"] = 3600
        _engine = create_engine(url, **kwargs)
    return _engine


def get_session():
    """
    [What] 获取会话工厂（延迟初始化）
    [Why] 配合延迟引擎
    [How] 首次调用时创建
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=_get_engine()
        )
    return _SessionLocal


def get_db():
    """
    [What] 获取数据库会话（依赖注入）
    [Why] FastAPI的依赖注入模式需要这个函数
    [How] 创建会话，请求结束后自动关闭
    """
    db = get_session()()
    try:
        yield db
    except Exception:
        logger.error("Request processing failed", exc_info=True)
        try:
            db.rollback()
        except Exception:
            logger.error("Session rollback failed", exc_info=True)
        raise
    finally:
        db.close()
