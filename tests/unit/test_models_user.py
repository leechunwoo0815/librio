# tests/unit/test_models_user.py
"""
[What] 用户模型单元测试
[Why] TDD：先写失败测试，再实现
[How] 测试用户模型的创建和属性
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User


@pytest.fixture
def db_session():
    """
    [What] 创建测试数据库会话
    [Why] 每个测试需要独立的数据库会话
    [How] 使用SQLite内存数据库
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_user(db_session):
    """
    [What] 测试创建用户
    [Why] 验证用户模型的基本创建功能
    [How] 创建用户实例，验证属性
    """
    user = User(parent_name="张三", phone="13800138000", openid="test_openid_123")
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert user.parent_name == "张三"
    assert user.phone == "13800138000"
    assert user.openid == "test_openid_123"
    assert user.is_deleted == 0


def test_user_unique_phone(db_session):
    """
    [What] 测试手机号唯一性约束
    [Why] 确保同一手机号不能注册两次
    [How] 尝试创建两个相同手机号的用户
    """
    user1 = User(parent_name="张三", phone="13800138000", openid="openid1")
    user2 = User(parent_name="李四", phone="13800138000", openid="openid2")

    db_session.add(user1)
    db_session.commit()

    with pytest.raises(Exception):  # 应抛出唯一性约束异常
        db_session.add(user2)
        db_session.commit()
