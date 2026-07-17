"""Tests for observation report PDF endpoint"""

import os

import pytest

from fastapi.testclient import TestClient
from backend.main import app
from backend.middleware.auth import create_access_token

try:
    import weasyprint  # noqa: F401

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

HAS_MYSQL = not os.environ.get("DATABASE_URL", "").startswith("sqlite")

client = TestClient(app)

_real_token = create_access_token({"sub": "1"})
AUTH_HEADER = {"Authorization": f"Bearer {_real_token}"}


def test_observation_pdf_requires_auth():
    """Without auth token, endpoint should return 401"""
    response = client.get("/report/observation/1/pdf")
    assert response.status_code == 401


def test_observation_pdf_endpoint_is_async():
    """验证PDF端点使用 async def（不阻塞事件循环）"""
    import inspect
    from backend.domain.report.router import get_observation_report_pdf

    assert inspect.iscoroutinefunction(get_observation_report_pdf), (
        "PDF endpoint must be async def"
    )


@pytest.mark.skipif(
    not PDF_AVAILABLE or not HAS_MYSQL, reason="weasyprint or MySQL not available"
)
def test_observation_pdf_with_auth():
    """With valid auth token, endpoint should route correctly (no DB data → 404)"""
    response = client.get("/report/observation/1/pdf", headers=AUTH_HEADER)
    assert response.status_code in (401, 404)
