# tests/conftest.py
"""
[What] 测试配置文件
[Why] 提供测试所需的fixtures和配置
[How] 使用pytest的conftest机制
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app


# [What] 创建测试数据库引擎
# [Why] 测试使用SQLite内存数据库，避免依赖MySQL
# [How] 使用StaticPool确保所有连接共享同一数据库
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# [What] 创建测试会话工厂
# [Why] 每个测试需要独立的数据库会话
# [How] 使用sessionmaker绑定测试引擎
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """
    [What] 覆盖数据库会话依赖
    [Why] 测试时使用测试数据库而非生产数据库
    [How] 使用FastAPI的dependency_overrides
    """
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session():
    """
    [What] 数据库会话fixture
    [Why] 每个测试函数需要独立的数据库会话
    [How] 创建会话，测试结束后回滚
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    [What] 测试客户端fixture
    [Why] 用于测试FastAPI端点
    [How] 创建TestClient，覆盖数据库依赖
    """
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
