"""Tests for monthly report endpoint — with test DB setup"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app
from backend.middleware.auth import create_access_token
from backend.domain.user.models import User

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

    # 创建测试用户，使 create_access_token({"sub": "1"}) 通过认证
    user = User(
        openid="test_report_openid", phone="13800138001", parent_name="报告测试用户"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    yield client, db, user
    Base.metadata.drop_all(bind=_engine)
    app.dependency_overrides.clear()
    db.close()


def test_monthly_report_requires_auth(http):
    """无认证令牌应返回 401"""
    client, _, _ = http
    response = client.get("/report/stats/monthly", params={"child_id": 1})
    assert response.status_code == 401, f"期望 401，实际 {response.status_code}"


def test_monthly_report_with_auth(http):
    """有有效令牌应正常路由"""
    client, _, user = http
    token = create_access_token({"sub": str(user.id)})
    response = client.get(
        "/report/stats/monthly",
        params={"child_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 无测试数据时可能返回 200（空数据）或 404（child 不存在）
    # 关键是走通了路由和认证，不是 401 或 500
    assert response.status_code in (200, 404), (
        f"月报路由返回异常 {response.status_code}"
    )
