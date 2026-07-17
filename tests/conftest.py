# tests/conftest.py
"""
[What] pytest全局配置和共享fixtures
[Why] 所有测试共享数据库和客户端配置
[How] 使用SQLite内存数据库，每个测试独立会话
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base
from backend.main import app
# 禁用测试中的定时任务
from backend.tasks.scheduler import scheduler
if scheduler.running:
    scheduler.shutdown(wait=False)


@pytest.fixture
def db_engine():
    """
    [What] 创建测试数据库引擎
    [Why] 使用SQLite内存数据库，测试间完全隔离
    [How] 每次测试创建新引擎
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """
    [What] 创建测试数据库会话
    [Why] 每个测试有独立的事务，测试结束自动回滚
    [How] 使用sessionmaker创建会话
    """
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    """
    [What] 创建FastAPI测试客户端
    [Why] 用于测试API端点
    [How] 使用TestClient包装FastAPI app
    """
    return TestClient(app)
