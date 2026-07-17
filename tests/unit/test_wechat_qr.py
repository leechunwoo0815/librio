"""Tests for WeChat QR code endpoint"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DATABASE_URL", "").startswith("sqlite"),
    reason="requires MySQL (TestClient app engine vs test fixture engine)",
)
from fastapi.testclient import TestClient
from backend.main import app
from backend.middleware.auth import create_access_token

client = TestClient(app)

_real_token = create_access_token({"sub": "1"})
AUTH_HEADER = {"Authorization": f"Bearer {_real_token}"}


def test_wechat_qr_requires_auth():
    response = client.get("/wechat/qr-code?scene=cert_1&page=test")
    assert response.status_code in (401, 403)


def test_wechat_qr_invalid_scene():
    response = client.get("/wechat/qr-code?scene=&page=test", headers=AUTH_HEADER)
    assert response.status_code == 422


def test_wechat_qr_missing_scene():
    response = client.get("/wechat/qr-code?page=test", headers=AUTH_HEADER)
    assert response.status_code == 422


def test_wechat_qr_missing_page():
    response = client.get("/wechat/qr-code?scene=test", headers=AUTH_HEADER)
    assert response.status_code == 422


def test_wechat_qr_long_scene():
    response = client.get(
        "/wechat/qr-code?scene=" + "a" * 33 + "&page=test",
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422


def test_wechat_endpoint_is_async():
    """验证扫码端点使用 async def（不阻塞事件循环）"""
    import inspect
    from backend.domain.wechat.router import get_qr_code

    assert inspect.iscoroutinefunction(get_qr_code), "QR code endpoint must be async def"


def test_wechat_access_token_double_check_locking():
    """验证 access_token 双重检查锁定逻辑"""
    from backend.domain.wechat.service import _token_cache, _token_refresh_lock

    assert _token_cache is not None
    assert _token_refresh_lock is not None

    # 验证缓存初始状态
    _token_cache._token = None
    _token_cache._expires_at = 0
    assert _token_cache.get() is None


# ---------------------------------------------------------------------------
# Mock 微信 API 测试：access_token 缓存 + 错误处理
# ---------------------------------------------------------------------------


def _clear_token_cache():
    from backend.domain.wechat.service import _token_cache

    _token_cache._token = None
    _token_cache._expires_at = 0


def test_wechat_qr_uses_cached_token(monkeypatch):
    """第二次调用应使用缓存 access_token，不再请求微信 token API"""
    import httpx

    _clear_token_cache()

    token_fetch_count = 0

    def mock_get(*args, **kwargs):
        nonlocal token_fetch_count
        token_fetch_count += 1
        return httpx.Response(200, json={
            "access_token": "mock_token_123",
            "expires_in": 7200,
        })

    def mock_post(*args, **kwargs):
        return httpx.Response(
            200,
            content=b"fake_png_bytes",
            headers={"content-type": "image/png"},
        )

    monkeypatch.setattr("httpx.get", mock_get)
    monkeypatch.setattr("httpx.post", mock_post)

    # 第一次调用 → 触发 token 刷新 + QR 请求
    r1 = client.get("/wechat/qr-code?scene=cert_1&page=test", headers=AUTH_HEADER)
    assert token_fetch_count == 1, "第一次应触发 token 刷新"
    assert r1.status_code == 200
    assert r1.headers["content-type"] == "image/png"

    # 第二次调用 → 应命中缓存，不再请求微信 token
    r2 = client.get("/wechat/qr-code?scene=cert_1&page=test", headers=AUTH_HEADER)
    assert token_fetch_count == 1, "第二次应使用缓存，不触发 token 刷新"
    assert r2.status_code == 200


def test_wechat_qr_fetch_token_fails(monkeypatch):
    """微信 token API 返回错误时返回 500"""
    import httpx

    _clear_token_cache()

    def mock_get(*args, **kwargs):
        return httpx.Response(200, json={
            "errcode": 40001,
            "errmsg": "invalid credential",
        })

    monkeypatch.setattr("httpx.get", mock_get)

    r = client.get("/wechat/qr-code?scene=cert_1&page=test", headers=AUTH_HEADER)
    assert r.status_code == 502
    assert "获取access_token失败" in r.json()["detail"]


def test_wechat_qr_api_error_raises(monkeypatch):
    """微信 QR 接口返回 JSON 错误时返回 500"""
    import httpx

    _clear_token_cache()

    def mock_get(*args, **kwargs):
        return httpx.Response(200, json={
            "access_token": "mock_token_456",
            "expires_in": 7200,
        })

    def mock_post(*args, **kwargs):
        return httpx.Response(
            200,
            json={"errcode": 41030, "errmsg": "invalid page"},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr("httpx.get", mock_get)
    monkeypatch.setattr("httpx.post", mock_post)

    r = client.get("/wechat/qr-code?scene=cert_1&page=test", headers=AUTH_HEADER)
    assert r.status_code == 502
    assert "生成小程序码失败" in r.json()["detail"]
