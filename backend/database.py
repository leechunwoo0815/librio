# backend/database.py
"""
[What] 数据库连接配置
[Why] 统一管理数据库会话和引擎
[How] 使用SQLAlchemy的create_engine和sessionmaker
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.config import get_settings

settings = get_settings()

# [What] 创建数据库引擎
# [Why] 引擎是SQLAlchemy与数据库交互的核心
# [How] 使用create_engine，设置连接池参数
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,           # 连接池大小
    max_overflow=20,        # 最大溢出连接数
    pool_pre_ping=True,     # 连接前ping检测
    echo=settings.DEBUG,    # 是否打印SQL语句
)

# [What] 创建会话工厂
# [Why] 每个请求需要独立的数据库会话
# [How] 使用sessionmaker绑定引擎
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# [What] 创建模型基类
# [Why] 所有模型需要继承同一个基类
# [How] 使用declarative_base()
Base = declarative_base()


def get_db():
    """
    [What] 获取数据库会话（依赖注入）
    [Why] FastAPI的依赖注入模式需要这个函数
    [How] 创建会话，请求结束后自动关闭
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
