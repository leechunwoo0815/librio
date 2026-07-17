# tests/unit/test_child_service.py
"""孩子服务单元测试"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.child.service import ChildService
from backend.domain.child.schemas import ChildCreate


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def child_service(db):
    return ChildService(db)


def test_create_child(child_service, db):
    user = User(openid="test_child_user", phone="13800138010")
    db.add(user)
    db.commit()

    child_data = ChildCreate(name="小明", age=7, grade="二年级")
    result = child_service.create_child(user.id, child_data)

    assert result.name == "小明"
    assert result.user_id == user.id
    assert result.age == 7


def test_can_borrow_books_observation(child_service, db):
    """观察期会员+已交押金可以借书"""
    user = User(openid="obs_user", phone="13800138011")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="测试",
        age=6,
        grade="一年级",
        status=Child.STATUS_OBSERVATION,
        deposit_status=1,
    )
    db.add(child)
    db.commit()

    assert child_service.can_borrow_books(child.id) is True


def test_can_borrow_books_official(child_service, db):
    """正式会员+已交押金可以借书"""
    user = User(openid="official_user", phone="13800138012")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="测试",
        age=6,
        grade="一年级",
        status=Child.STATUS_OFFICIAL,
        deposit_status=1,
    )
    db.add(child)
    db.commit()

    assert child_service.can_borrow_books(child.id) is True


def test_can_borrow_books_expired(child_service, db):
    """过期会员不可借书"""
    user = User(openid="expired_user", phone="13800138013")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id, name="测试", age=6, grade="一年级", status=Child.STATUS_EXPIRED
    )
    db.add(child)
    db.commit()

    assert child_service.can_borrow_books(child.id) is False


def test_can_borrow_books_child_not_found(child_service, db):
    """不存在的孩子不可借书"""
    from backend.common.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        child_service.can_borrow_books(999)
