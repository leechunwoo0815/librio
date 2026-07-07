# tests/unit/test_models_child.py
"""
[What] 孩子模型单元测试
[Why] TDD：先写失败测试，验证Child模型的创建和约束
[How] 使用SQLite内存数据库测试Child模型
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child


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


def test_create_child(db_session):
    """
    [What] 测试创建孩子
    [Why] 验证孩子模型的基本创建功能
    [How] 创建parent user和孩子实例
    """
    parent = User(openid="test_openid_child")
    db_session.add(parent)
    db_session.commit()

    child = Child(
        user_id=parent.id,
        name="小明",
        age=7,
        grade="二年级",
    )
    db_session.add(child)
    db_session.commit()

    assert child.id is not None
    assert child.user_id == parent.id
    assert child.name == "小明"
    assert child.age == 7
    assert child.status == 0  # 默认体验用户
    assert child.is_deleted == 0


def test_child_relationship_with_parent(db_session):
    """
    [What] 测试孩子与家长的关联关系
    [Why] 验证外键关系和一对多映射
    [How] 创建parent和两个children
    """
    parent = User(openid="test_openid_multi")
    db_session.add(parent)
    db_session.commit()

    child1 = Child(user_id=parent.id, name="小明", age=7, grade="二年级")
    child2 = Child(user_id=parent.id, name="小红", age=5, grade="幼儿园大班")
    db_session.add_all([child1, child2])
    db_session.commit()

    children = db_session.query(Child).filter(Child.user_id == parent.id).all()
    assert len(children) == 2
    assert children[0].name in ("小明", "小红")
    assert children[1].name in ("小明", "小红")


def test_child_member_status_flow(db_session):
    """
    [What] 测试孩子会员状态流转
    [Why] 验证状态枚举和流转逻辑
    [How] 依次设置不同状态并验证
    """
    parent = User(openid="test_openid_status")
    db_session.add(parent)
    db_session.commit()

    child = Child(user_id=parent.id, name="小明", age=7, grade="二年级")
    db_session.add(child)
    db_session.commit()

    # 初始状态：体验用户
    assert child.status == 0

    # 支付观察期后：观察期会员
    child.status = 1
    db_session.commit()
    assert child.status == 1

    # 评估通过支付年费后：正式会员
    child.status = 2
    db_session.commit()
    assert child.status == 2

    # 到期后：已过期
    child.status = 3
    db_session.commit()
    assert child.status == 3
