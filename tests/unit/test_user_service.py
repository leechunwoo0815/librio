# tests/unit/test_user_service.py
"""
[What] 用户服务单元测试
[Why] TDD：先写失败测试，再实现
[How] 测试用户创建、查询等功能
"""

import pytest
from unittest.mock import MagicMock
from backend.services.user_service import UserService
from backend.schemas.user import UserCreate


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def user_service(mock_repo):
    return UserService(mock_repo)


def test_create_user(user_service, mock_repo):
    """
    [What] 测试创建用户
    [Why] 验证用户创建逻辑
    [How] Mock仓库层，测试服务层逻辑
    """
    user_data = UserCreate(
        parent_name="张三",
        phone="13800138000",
        openid="test_openid"
    )

    mock_repo.get_by_phone.return_value = None
    mock_repo.create.return_value = MagicMock(id=1, **user_data.dict())

    result = user_service.create_user(user_data)

    assert result.id == 1
    assert result.phone == "13800138000"
    mock_repo.create.assert_called_once()


def test_create_user_duplicate_phone(user_service, mock_repo):
    """
    [What] 测试重复手机号创建用户
    [Why] 验证手机号唯一性校验
    [How] Mock返回已存在的用户
    """
    user_data = UserCreate(
        parent_name="张三",
        phone="13800138000",
        openid="test_openid"
    )

    mock_repo.get_by_phone.return_value = MagicMock(id=1)

    with pytest.raises(ValueError, match="手机号已注册"):
        user_service.create_user(user_data)
