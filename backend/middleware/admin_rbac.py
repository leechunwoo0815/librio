"""RBAC 权限中间件 — require_perm 依赖注入"""

import logging

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.common.exceptions import ForbiddenError
from backend.database import get_db
from backend.domain.admin.models import Admin
from backend.middleware.admin_auth import get_current_admin

logger = logging.getLogger(__name__)


def require_perm(*perm_codes: str):
    """RBAC 权限检查依赖注入

    用法:
        admin=Depends(require_perm("user.create"))
        admin=Depends(require_perm("user.create", "user.edit"))
    """
    def perm_checker(
        admin: Admin = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ) -> Admin:
        from backend.domain.admin.services.account_service import AdminAccountService
        if not any(AdminAccountService(db).has_permission(admin, code) for code in perm_codes):
            logger.warning("Permission denied: admin_id=%d, username=%s, required=%s, role_id=%d", admin.id, admin.username, perm_codes, admin.admin_role_id)
            raise ForbiddenError("权限不足")
        return admin
    return perm_checker
