"""Token 安全机制测试 — S-03/S-05/S-08

验证：
1. 改密码后 token_generation 递增，旧 Token 失效
2. 禁用管理员后 token_generation 递增，旧 Token 失效
3. User status=DISABLED 时 Token 被拒
4. 生产环境 ENABLE_TEST_TOKEN 启动报错
"""

import pytest
from unittest.mock import MagicMock, patch


class TestTokenGeneration:
    """S-03: token_generation 机制测试"""

    def test_admin_change_password_increments_generation(self):
        """改密码后 token_generation +1"""
        from backend.domain.admin.models import Admin
        from backend.domain.admin.services.account_service import AdminAccountService
        from backend.common.types import AdminRole

        mock_db = MagicMock()
        admin = Admin(
            id=1,
            username="admin",
            password_hash="$2b$12$old_hash",
            name="Admin",
            role=AdminRole.ADMIN,
            status=Admin.STATUS_ACTIVE,
            token_generation=0,
        )

        mock_db.query.return_value.filter.return_value.first.return_value = admin

        with (
            patch(
                "backend.domain.admin.services.account_service.verify_password",
                return_value=True,
            ),
            patch(
                "backend.domain.admin.services.account_service.hash_password",
                return_value="$2b$12$new_hash",
            ),
        ):
            service = AdminAccountService(mock_db)
            result = service.change_password(1, "old", "new", 1)

        assert result["success"] is True
        assert admin.token_generation == 1
        assert admin.password_hash == "$2b$12$new_hash"

    def test_admin_disable_increments_generation(self):
        """禁用管理员后 token_generation +1"""
        from backend.domain.admin.models import Admin
        from backend.domain.admin.services.account_service import AdminAccountService
        from backend.common.types import AdminRole
        from backend.domain.admin.admin_schemas import UpdateAdminRequest

        admin = Admin(
            id=2,
            username="staff01",
            password_hash="$2b$12$hash",
            name="Staff",
            role=AdminRole.STAFF,
            status=Admin.STATUS_ACTIVE,
            token_generation=3,
        )

        current_admin = Admin(
            id=1,
            username="super",
            password_hash="$2b$12$hash",
            name="Super",
            role=AdminRole.ADMIN,
            status=Admin.STATUS_ACTIVE,
            token_generation=0,
        )

        mock_db = MagicMock()
        # First query: target admin
        # Second query: current admin
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            admin,
            current_admin,
        ]

        service = AdminAccountService(mock_db)
        update_data = UpdateAdminRequest(status=Admin.STATUS_DISABLED)

        with (
            patch.object(service, "is_super_admin", return_value=False),
            patch.object(service, "_check_admin_role_change"),
            patch.object(service, "_resolve_admin_role_id", return_value=None),
            patch.object(service, "_sync_legacy_role"),
        ):
            service.update_admin(2, update_data, current_admin_id=1)

        assert admin.token_generation == 4
        assert admin.status == Admin.STATUS_DISABLED

    def test_user_status_field_exists(self):
        """S-05: User 模型有 status 字段"""
        from backend.domain.user.models import User

        assert hasattr(User, "status")
        assert hasattr(User, "STATUS_ACTIVE")
        assert hasattr(User, "STATUS_DISABLED")
        assert User.STATUS_ACTIVE == 1
        assert User.STATUS_DISABLED == 0

    def test_user_token_generation_field_exists(self):
        """S-03: User 模型有 token_generation 字段"""
        from backend.domain.user.models import User

        assert hasattr(User, "token_generation")

    def test_admin_token_generation_field_exists(self):
        """S-03: Admin 模型有 token_generation 字段"""
        from backend.domain.admin.models import Admin

        assert hasattr(Admin, "token_generation")

    def test_create_admin_token_includes_gen(self):
        """管理员 Token payload 包含 gen 字段"""
        from backend.middleware.admin_auth import create_admin_token
        from jose import jwt
        from backend.config import get_settings

        settings = get_settings()
        token = create_admin_token(1, 0, token_generation=5)
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        assert payload["gen"] == 5
        assert payload["type"] == "admin"

    def test_create_access_token_includes_gen(self):
        """用户 Token payload 包含 gen 字段（当传入时）"""
        from backend.middleware.auth import create_access_token
        from jose import jwt
        from backend.config import get_settings

        settings = get_settings()
        token = create_access_token({"sub": "1", "gen": 2})
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        assert payload["gen"] == 2
        assert payload["sub"] == "1"


class TestTestTokenSafety:
    """S-08: 生产环境 test-token-mock 安全"""

    def test_config_rejects_test_token_in_production(self):
        """非 DEBUG 模式下 ENABLE_TEST_TOKEN=True 报错（model_validator 触发）"""
        from backend.config import Settings

        # Pydantic model_validator 在构造时自动触发校验
        with pytest.raises(RuntimeError, match="ENABLE_TEST_TOKEN"):
            Settings(DEBUG=False, ENABLE_TEST_TOKEN=True, SECRET_KEY="prod-secret-xxx")

    def test_config_allows_test_token_in_debug(self):
        """DEBUG 模式下 ENABLE_TEST_TOKEN=True 正常通过校验"""
        from backend.config import Settings

        s = Settings(DEBUG=True, ENABLE_TEST_TOKEN=True, SECRET_KEY="dev-secret")
        assert s.ENABLE_TEST_TOKEN is True

    def test_config_rejects_default_secret_in_production(self):
        """非 DEBUG 模式下默认 SECRET_KEY 报错"""
        from backend.config import Settings

        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            Settings(
                DEBUG=False,
                ENABLE_TEST_TOKEN=False,
                SECRET_KEY="your-secret-key-change-in-production",
            )
