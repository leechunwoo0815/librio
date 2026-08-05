# tests/unit/test_f13_status_change_guard.py
"""F13 会员状态变更/复活权限收敛 — 超管限定 + 二次确认 + from→to 审计

专家口径（20260805）：会员状态变更/复活收归超管（staff 只读）+
强制二次确认参数（confirmed=true）+ from→to 全量 OperationLog。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.exceptions import ValidationError
from backend.common.types import MemberStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


@pytest.fixture
def http_client_db():
    """HTTP 层 fixture：StaticPool 共享连接，供 TestClient 跨线程使用"""
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    from backend.database import get_db
    from backend.main import app

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, session
    app.dependency_overrides.clear()
    session.close()


def _mk_child(db, status=MemberStatus.TRIAL):
    user = User(openid="f13parent", phone="13800006666")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F13",
        age=7,
        grade="二年级",
        status=status,
    )
    db.add(child)
    db.commit()
    return child


def _seed_admin(http_db, role_code: str, username: str):
    """种子角色并创建指定角色管理员，返回 (client, db, headers)"""
    from jose import jwt

    from backend.domain.admin.models import Admin
    from backend.domain.admin.rbac_models import Role
    from backend.config import get_settings
    from backend.seeds.seed_rbac import (
        seed_permissions,
        seed_role_permissions,
        seed_roles,
    )

    client, db = http_db
    seed_roles(db)
    seed_permissions(db)
    seed_role_permissions(db)
    db.flush()
    role = db.query(Role).filter(Role.code == role_code).first()
    assert role is not None
    admin = Admin(
        username=username,
        name=username,
        admin_role_id=role.id,
        password_hash="x",
    )
    db.add(admin)
    db.commit()
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(admin.id),
            "role": 0 if role_code == "super_admin" else 1,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "admin",
            "jti": f"f13-{username}",
            "gen": 0,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return client, db, {"Authorization": f"Bearer {token}"}


class TestStatusUpdateServiceGuard:
    def test_update_status_requires_confirmed(self, db):
        """无 confirmed=true 必须拒绝（二次确认强制）"""
        from backend.domain.child.schemas import ChildStatusUpdate
        from backend.domain.child.service import ChildService

        child = _mk_child(db)
        with pytest.raises(ValidationError):
            ChildService(db).update_status(
                child.id, ChildStatusUpdate(status=MemberStatus.OBSERVATION)
            )

    def test_update_status_confirmed_writes_from_to_log(self, db):
        """confirmed=true 成功迁移且落 from→to OperationLog"""
        from backend.domain.admin.models import OperationLog
        from backend.domain.child.schemas import ChildStatusUpdate
        from backend.domain.child.service import ChildService

        child = _mk_child(db)
        ChildService(db).update_status(
            child.id,
            ChildStatusUpdate(status=MemberStatus.OBSERVATION, confirmed=True),
            admin_id=7,
        )
        db.refresh(child)
        assert child.status == MemberStatus.OBSERVATION
        log = (
            db.query(OperationLog)
            .filter(
                OperationLog.admin_id == 7, OperationLog.operation == "update_status"
            )
            .first()
        )
        assert log is not None
        assert log.module == "child"
        assert "0" in log.content and "1" in log.content
        assert "→" in log.content

    def test_status_update_without_admin_id_skips_log(self, db):
        """无 admin_id（非管理端直调）不写审计，但迁移合法仍需确认"""
        from backend.domain.admin.models import OperationLog
        from backend.domain.child.schemas import ChildStatusUpdate
        from backend.domain.child.service import ChildService

        child = _mk_child(db)
        ChildService(db).update_status(
            child.id,
            ChildStatusUpdate(status=MemberStatus.OBSERVATION, confirmed=True),
        )
        count = (
            db.query(OperationLog)
            .filter(OperationLog.operation == "update_status")
            .count()
        )
        assert count == 0


class TestStatusUpdateHttpGuard:
    def test_staff_cannot_change_status(self, http_client_db):
        """staff（含 child.edit 权限）改状态 → 403"""
        db = http_client_db[1]
        child = _mk_child(db, status=MemberStatus.TRIAL)
        client, _, headers = _seed_admin(http_client_db, "staff", "f13_staff")
        r = client.put(
            f"/child/{child.id}/status",
            json={"status": MemberStatus.OBSERVATION, "confirmed": True},
            headers=headers,
        )
        assert r.status_code == 403

    def test_super_admin_requires_confirm(self, http_client_db):
        """超管不传 confirmed → 422"""
        db = http_client_db[1]
        child = _mk_child(db, status=MemberStatus.TRIAL)
        client, _, headers = _seed_admin(http_client_db, "super_admin", "f13_super")
        r = client.put(
            f"/child/{child.id}/status",
            json={"status": MemberStatus.OBSERVATION},
            headers=headers,
        )
        assert r.status_code == 422

    def test_super_admin_confirmed_ok(self, http_client_db):
        """超管 + confirmed=true → 200 且状态迁移生效"""
        db = http_client_db[1]
        child = _mk_child(db, status=MemberStatus.TRIAL)
        client, db2, headers = _seed_admin(http_client_db, "super_admin", "f13_super2")
        r = client.put(
            f"/child/{child.id}/status",
            json={"status": MemberStatus.OBSERVATION, "confirmed": True},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        db2.refresh(child)
        assert child.status == MemberStatus.OBSERVATION


class TestReviveGuard:
    def test_staff_cannot_revive(self, http_client_db):
        """staff 复活 → 403"""
        db = http_client_db[1]
        child = _mk_child(db, status=MemberStatus.EXITED)
        client, _, headers = _seed_admin(http_client_db, "staff", "f13_rev_staff")
        r = client.post(
            f"/admin/api/children/{child.id}/revive",
            json={"confirmed": True},
            headers=headers,
        )
        assert r.status_code == 403

    def test_revive_requires_confirm(self, http_client_db):
        """超管不传 confirmed → 422"""
        db = http_client_db[1]
        child = _mk_child(db, status=MemberStatus.EXITED)
        client, _, headers = _seed_admin(http_client_db, "super_admin", "f13_rev_super")
        r = client.post(
            f"/admin/api/children/{child.id}/revive",
            json={},
            headers=headers,
        )
        assert r.status_code == 422

    def test_revive_confirmed_ok_with_log(self, http_client_db):
        """超管 + confirmed=true → 200，EXITED→TRIAL 且审计含 from→to"""
        from backend.domain.admin.models import OperationLog

        db = http_client_db[1]
        child = _mk_child(db, status=MemberStatus.EXITED)
        client, db2, headers = _seed_admin(http_client_db, "super_admin", "f13_rev_ok")
        r = client.post(
            f"/admin/api/children/{child.id}/revive",
            json={"confirmed": True},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        db2.refresh(child)
        assert child.status == MemberStatus.TRIAL
        log = (
            db2.query(OperationLog)
            .filter(OperationLog.operation == "revive_child")
            .first()
        )
        assert log is not None
        assert "EXITED" in log.content and "TRIAL" in log.content
        assert "→" in log.content
