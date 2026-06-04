# tests/unit/test_auth.py
"""
[What] 认证中间件单元测试
[Why] TDD：先写失败测试
[How] 测试JWT生成和验证
"""

import pytest
from backend.middleware.auth import create_access_token, verify_token


def test_create_access_token():
    """
    [What] 测试创建JWT Token
    [Why] 验证Token生成逻辑
    [How] 创建Token并验证内容
    """
    token = create_access_token(data={"sub": "1"})
    assert token is not None
    assert len(token) > 0


def test_verify_token():
    """
    [What] 测试验证JWT Token
    [Why] 验证Token解析逻辑
    [How] 创建Token后验证
    """
    token = create_access_token(data={"sub": "1"})
    payload = verify_token(token)
    assert payload["sub"] == "1"


def test_verify_invalid_token():
    """
    [What] 测试无效Token
    [Why] 验证Token验证的异常处理
    [How] 使用无效Token验证
    """
    with pytest.raises(Exception):
        verify_token("invalid_token")