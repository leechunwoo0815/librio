# backend/domain/admin/admin_auth_router.py
"""管理员认证路由 — 登录/登出"""

import logging
import time

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy.orm import Session

from backend.common.base_schema import BaseSchema
from backend.database import get_db
from backend.domain.admin.models import Admin
from backend.domain.admin.services.account_service import AdminAccountService
from backend.middleware.admin_auth import create_admin_token, get_current_admin
from backend.middleware.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["管理认证"])

# 暴力破解防护：记录失败次数 {(username, ip): (count, first_fail_time)}
_login_failures: dict[tuple[str, str], tuple[int, float]] = {}
_MAX_FAILURES = 5
_LOCKOUT_SECONDS = 900  # 15 分钟


class AdminLoginRequest(BaseSchema):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class AdminLoginResponse(BaseSchema):
    token: str
    admin_id: int
    name: str
    role: int
    role_code: str | None = None
    permissions: list[str] = []
    data_scope: str = "none"


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    dependencies=[Depends(rate_limit(10, 60))],
)
def admin_login(
    data: AdminLoginRequest, request: Request, db: Session = Depends(get_db)
):
    """管理员登录"""
    # 暴力破解防护
    client_ip = request.client.host if request.client else "unknown"
    key = (data.username, client_ip)
    if key in _login_failures:
        count, first_time = _login_failures[key]
        if count >= _MAX_FAILURES and (time.time() - first_time) < _LOCKOUT_SECONDS:
            remaining = int(_LOCKOUT_SECONDS - (time.time() - first_time))
            from backend.common.exceptions import RateLimitError

            raise RateLimitError(f"登录失败次数过多，请 {remaining} 秒后重试")
        if (time.time() - first_time) >= _LOCKOUT_SECONDS:
            del _login_failures[key]

    admin_service = AdminAccountService(db)
    admin = admin_service.authenticate_admin(data.username, data.password)

    if not admin:
        # 记录失败
        if key in _login_failures:
            count, first_time = _login_failures[key]
            _login_failures[key] = (count + 1, first_time)
        else:
            _login_failures[key] = (1, time.time())
        logger.warning("Login failed: username=%s, ip=%s", data.username, client_ip)
        from backend.common.exceptions import UnauthorizedError

        raise UnauthorizedError("用户名或密码错误")

    if admin.status != Admin.STATUS_ACTIVE:
        logger.warning(
            "Login blocked: username=%s, ip=%s, status=%s",
            data.username,
            client_ip,
            admin.status,
        )
        from backend.common.exceptions import ForbiddenError

        raise ForbiddenError("账号已禁用")

    # 登录成功，清除失败记录
    _login_failures.pop(key, None)

    token = create_admin_token(admin.id, admin.role)
    logger.info(f"Admin login: {admin.username} (id={admin.id})")

    permissions = list(admin_service.get_permission_codes(admin))

    return AdminLoginResponse(
        token=token,
        admin_id=admin.id,
        name=admin.name or admin.username,
        role=admin.role,
        role_code=admin_service.get_role_code(admin),
        permissions=permissions,
        data_scope=admin_service.get_data_scope(admin),
    )


@router.get("/api/me/permissions")
def get_my_permissions(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取当前管理员的权限列表"""
    return {
        "permissions": list(AdminAccountService(db).get_permission_codes(admin)),
        "role_code": AdminAccountService(db).get_role_code(admin),
        "name": admin.name or admin.username,
        "data_scope": AdminAccountService(db).get_data_scope(admin),
    }


@router.post("/logout")
def admin_logout():
    """管理员登出（客户端清 token）"""
    return {"success": True}
