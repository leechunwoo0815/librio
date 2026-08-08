"""F-061 回归：观察期报告手动生成入口复用分布式锁

原实现：scheduler 任务持 job:check_observation_expiry 锁，admin 手动入口无锁 →
并发双生成（R10 报告）。修复后手动入口复用同一把锁，锁被占时 409。
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.middleware.admin_auth import create_admin_token
from backend.domain.admin.models import Admin
from backend.domain.admin.rbac_models import Permission, Role

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture
def http():
    Base.metadata.create_all(bind=_engine)
    Session = sessionmaker(bind=_engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    db = Session()

    role = Role(code="super_admin", name="超级管理员", is_system=True)
    db.add(role)
    db.add(
        Permission(
            code="report.generate",
            name="生成报告",
            group_name="report",
            is_system=True,
        )
    )
    db.commit()
    admin = Admin(
        username="f061_admin",
        password_hash="x",
        name="F061",
        role=0,
        status=Admin.STATUS_ACTIVE,
        token_generation=0,
        admin_role_id=role.id,
    )
    db.add(admin)
    db.commit()

    token = create_admin_token(admin.id, role=0, token_generation=0)
    yield client, db, token
    Base.metadata.drop_all(bind=_engine)
    app.dependency_overrides.clear()
    db.close()


def _monkeypatch_redis_lock(monkeypatch, acquired: bool) -> list:
    """替换 redis_lock 为可注入 acquired 的 contextmanager"""
    from backend.common import distributed_lock

    lock_keys = []

    @contextmanager
    def _fake_lock(lock_key: str, timeout: int = 300):
        lock_keys.append((lock_key, timeout))
        yield acquired

    monkeypatch.setattr(distributed_lock, "redis_lock", _fake_lock)
    return lock_keys


def test_generate_locked_returns_409(http, monkeypatch):
    """锁被 scheduler/他人持有 → 409，不得双生成"""
    client, _, token = http
    lock_keys = _monkeypatch_redis_lock(monkeypatch, acquired=False)

    resp = client.post(
        "/admin/api/reports/observation/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409, resp.text
    assert "正在生成中" in resp.json().get("detail", "")
    # F-061 核心：必须与 scheduler 任务同一把锁（job:check_observation_expiry）才能真正互斥
    assert lock_keys == [("job:check_observation_expiry", 600)]


def test_generate_unlocked_succeeds(http, monkeypatch):
    """锁可用 → 正常生成（无到期孩子时生成 0 份）"""
    client, _, token = http
    _monkeypatch_redis_lock(monkeypatch, acquired=True)

    resp = client.post(
        "/admin/api/reports/observation/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success") is True
