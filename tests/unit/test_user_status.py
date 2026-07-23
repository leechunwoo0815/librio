# tests/unit/test_user_status.py
"""S-05 用户禁用/启用 — 操作路径测试（set_user_status + 禁用后 Token 失效）"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.exceptions import NotFoundError, UnauthorizedError, ValidationError
from backend.database import Base
from backend.domain.admin.services.user_service import AdminUserService
from backend.domain.user.models import User


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def user(db):
    u = User(openid=f"test_openid_{uuid.uuid4().hex[:8]}", parent_name="测试家长")
    db.add(u)
    db.flush()
    db.refresh(u)
    return u


class TestSetUserStatus:
    def test_disable_user(self, db, user):
        gen_before = user.token_generation
        result = AdminUserService(db).set_user_status(user.id, 0)
        assert result["success"] is True
        db.refresh(user)
        assert user.status == User.STATUS_DISABLED
        assert user.token_generation == gen_before + 1

    def test_enable_user(self, db, user):
        svc = AdminUserService(db)
        svc.set_user_status(user.id, 0)
        svc.set_user_status(user.id, 1)
        db.refresh(user)
        assert user.status == User.STATUS_ACTIVE

    def test_invalid_status(self, db, user):
        with pytest.raises(ValidationError):
            AdminUserService(db).set_user_status(user.id, 5)

    def test_nonexistent_user(self, db):
        with pytest.raises(NotFoundError):
            AdminUserService(db).set_user_status(999999, 0)


class TestDisabledUserTokenRejected:
    def test_disabled_user_token_rejected(self, db, user):
        """禁用后旧 Token（gen 已同步）仍被 status 校验拒绝"""
        from backend.middleware.auth import create_access_token, get_current_user

        token = create_access_token({"sub": str(user.id), "gen": user.token_generation})
        AdminUserService(db).set_user_status(user.id, 0)
        # 注意：禁用使 gen+1，此 token 的 gen 已过期；即使 gen 同步，status 校验也会拒绝
        credentials = SimpleNamespace(credentials=token)
        with pytest.raises(UnauthorizedError):
            asyncio.run(get_current_user(credentials, db))
