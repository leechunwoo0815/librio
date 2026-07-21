"""Tests for monthly report endpoint"""

from fastapi.testclient import TestClient
from backend.main import app
from backend.middleware.auth import create_access_token

client = TestClient(app)

_real_token = create_access_token({"sub": "1"})
AUTH_HEADER = {"Authorization": f"Bearer {_real_token}"}


def test_monthly_report_requires_auth():
    """无认证令牌应返回 401"""
    response = client.get("/report/stats/monthly", params={"child_id": 1})
    assert response.status_code == 401, f"期望 401，实际 {response.status_code}"


def test_monthly_report_with_auth():
    """有有效令牌应正常路由"""
    response = client.get(
        "/report/stats/monthly",
        params={"child_id": 1},
        headers=AUTH_HEADER,
    )
    # 无测试数据时可能返回 200（空数据）或 404（child 不存在）
    # 关键是走通了路由和认证，不是 401 或 500
    assert response.status_code in (200, 404), (
        f"月报路由返回异常 {response.status_code}"
    )
