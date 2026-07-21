# backend/domain/admin/services/account_service.py
"""管理端账号 Service — 从 AdminService 拆分出来的独立域服务。"""

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.common.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.domain.admin.models import Admin
from backend.utils.password import hash_password, verify_password


def assert_not_last_super_admin(db: Session, exclude_admin_id: int):
    """如果操作后 enabled super_admin 数量为 0，拒绝操作。"""
    from backend.domain.admin.rbac_models import Role

    super_admin_role = (
        db.query(Role)
        .filter(Role.code == "super_admin", Role.is_deleted == 0)
        .first()
    )
    if not super_admin_role:
        return

    count = (
        db.query(Admin)
        .filter(
            Admin.admin_role_id == super_admin_role.id,
            Admin.is_deleted == 0,
            Admin.status == Admin.STATUS_ACTIVE,
            Admin.id != exclude_admin_id,
        )
        .count()
    )
    if count == 0:
        raise ValidationError("至少需要保留一个启用的超级管理员")


class AdminAccountService:
    """管理员账号：认证、CRUD。"""

    def __init__(self, db: Session):
        self.db = db

    def get_role_code(self, admin: Admin) -> str | None:
        if admin.role_ref:
            return admin.role_ref.code
        return None

    def is_super_admin(self, admin: Admin) -> bool:
        return self.get_role_code(admin) == "super_admin"

    def validate_admin_token(self, token: str) -> dict | None:
        """Validate admin JWT token and return admin info dict or None.

        Architecture: moved out of admin_page_router.py per audit — Router
        must not contain try/except or direct DB queries (CLAUDE.md 三).
        """
        from jose import JWTError, jwt
        from backend.config import get_settings

        settings = get_settings()
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            if payload.get("type") != "admin":
                return None
            admin_id = payload.get("sub")
            if not admin_id:
                return None

            admin = (
                self.db.query(Admin)
                .filter(
                    Admin.id == int(admin_id),
                    Admin.is_deleted == 0,
                    Admin.status == Admin.STATUS_ACTIVE,
                )
                .first()
            )
            if not admin:
                return None

            permissions = list(self.get_permission_codes(admin))
            return {
                "id": admin.id,
                "name": admin.name or admin.username,
                "role": admin.role,
                "role_code": self.get_role_code(admin),
                "permissions": permissions,
            }
        except JWTError:
            return None

    def authenticate_admin(self, username: str, password: str) -> Optional[Admin]:
        """Authenticate admin by username and password. Returns Admin or None."""
        admin = (
            self.db.query(Admin)
            .filter(
                Admin.username == username,
                Admin.is_deleted == 0,
            )
            .first()
        )
        if not admin or not verify_password(password, admin.password_hash):
            return None
        return admin

    def _role_name(self, admin: Admin) -> str:
        if admin.role_ref:
            return admin.role_ref.name
        return {0: "超级管理员", 1: "运营人员", 2: "教师"}.get(admin.role or 1, "未知")

    def list_admins(self, page: int = 1, page_size: int = 20) -> dict:
        """获取管理员列表 — 带分页"""
        total = self.db.query(Admin).filter(Admin.is_deleted == 0).count()
        admins = (
            self.db.query(Admin)
            .filter(Admin.is_deleted == 0)
            .order_by(Admin.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "items": [
                {
                    "id": a.id,
                    "username": a.username,
                    "name": a.name,
                    "role": a.role,
                    "admin_role_id": a.admin_role_id,
                    "teacher_id": a.teacher_id,
                    "role_name": self._role_name(a),
                    "status": a.status,
                    "create_time": a.create_time.isoformat() if a.create_time else None,
                }
                for a in admins
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def get_admin(self, admin_id: int) -> dict:
        """获取单个管理员信息"""
        target = (
            self.db.query(Admin)
            .filter(Admin.id == admin_id, Admin.is_deleted == 0)
            .first()
        )
        if not target:
            raise NotFoundError("管理员不存在")

        return {
            "id": target.id,
            "username": target.username,
            "name": target.name,
            "role": target.role,
            "admin_role_id": target.admin_role_id,
            "teacher_id": target.teacher_id,
            "role_name": self._role_name(target),
            "phone": target.phone,
            "status": target.status,
            "last_login": target.last_login.isoformat()
            if hasattr(target, "last_login") and target.last_login
            else None,
            "create_time": target.create_time.isoformat()
            if target.create_time
            else None,
        }

    def _resolve_admin_role_id(self, data) -> int | None:
        if data.admin_role_id is not None:
            from backend.domain.admin.rbac_models import Role

            role = (
                self.db.query(Role)
                .filter(Role.id == data.admin_role_id, Role.is_deleted == 0)
                .first()
            )
            if not role:
                raise ValidationError("指定的角色不存在")
            return role.id
        legacy_map = {0: "super_admin", 1: "staff", 2: "teacher"}
        code = legacy_map.get(data.role, "staff")
        from backend.domain.admin.rbac_models import Role

        role = (
            self.db.query(Role).filter(Role.code == code, Role.is_deleted == 0).first()
        )
        return role.id if role else None

    def create_admin(self, data, current_admin_id: int) -> dict:
        """创建管理员"""
        existing = self.db.query(Admin).filter(Admin.username == data.username).first()
        if existing:
            raise ValidationError("用户名已存在")

        new_admin = Admin(
            username=data.username,
            name=data.name or data.username,
            role=data.role,
            admin_role_id=self._resolve_admin_role_id(data),
            teacher_id=data.teacher_id if data.teacher_id else None,
            status=1,
        )
        new_admin.password_hash = hash_password(data.password)
        self.db.add(new_admin)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValidationError("用户名已存在（并发创建）")
        self.db.refresh(new_admin)

        return {
            "id": new_admin.id,
            "username": new_admin.username,
            "name": new_admin.name,
            "role": new_admin.role,
            "admin_role_id": new_admin.admin_role_id,
            "teacher_id": new_admin.teacher_id,
            "message": "管理员创建成功",
        }

    def _check_admin_role_change(self, target: Admin, data, current: Admin):
        if target.id == current.id:
            if (
                data.admin_role_id is not None
                and data.admin_role_id != target.admin_role_id
            ) or (data.role is not None and data.role != target.role):
                raise ForbiddenError("不能修改自己的角色")
        if data.admin_role_id is not None:
            from backend.domain.admin.rbac_models import Role

            role = (
                self.db.query(Role)
                .filter(Role.id == data.admin_role_id, Role.is_deleted == 0)
                .first()
            )
            if not role:
                raise ValidationError("指定的角色不存在")

    def _sync_legacy_role(self, target: Admin):
        """同步 legacy role 字段与 admin_role_id 保持一致"""
        if not target.admin_role_id:
            return
        from backend.domain.admin.rbac_models import Role

        role_obj = self.db.query(Role).filter(Role.id == target.admin_role_id).first()
        if role_obj:
            legacy_map = {"super_admin": 0, "staff": 1, "teacher": 2}
            target.role = legacy_map.get(role_obj.code, 1)

    def update_admin(self, admin_id: int, data, current_admin_id: int) -> dict:
        """更新管理员"""
        target = (
            self.db.query(Admin)
            .filter(Admin.id == admin_id, Admin.is_deleted == 0)
            .first()
        )
        if not target:
            raise NotFoundError("管理员不存在")

        current = self.db.query(Admin).filter(Admin.id == current_admin_id).first()

        self._check_admin_role_change(target, data, current)

        # R4-4: 最后一个超管保护（禁用或降权时）
        if self.is_super_admin(target):
            if data.status is not None and data.status == Admin.STATUS_DISABLED:
                assert_not_last_super_admin(self.db, target.id)

        if (
            data.status is not None
            and target.id == current.id
            and data.status != target.status
        ):
            raise ForbiddenError("不能修改自己的状态")

        update_data = data.model_dump(exclude_unset=True)
        allowed_fields = ["name", "role", "status", "phone", "teacher_id"]
        for key, value in update_data.items():
            if key in allowed_fields:
                setattr(target, key, value)
        if "admin_role_id" in update_data:
            target.admin_role_id = self._resolve_admin_role_id(data)
            # R4-4: 最后一个超管保护（降权）
            if self.is_super_admin(target):
                from backend.domain.admin.rbac_models import Role

                new_role = (
                    self.db.query(Role)
                    .filter(
                        Role.id == target.admin_role_id, Role.is_deleted == 0
                    )
                    .first()
                )
                if new_role and new_role.code != "super_admin":
                    assert_not_last_super_admin(self.db, target.id)
            self._sync_legacy_role(target)
        elif "role" in update_data:
            target.admin_role_id = self._resolve_admin_role_id(data)

        if data.password:
            target.password_hash = hash_password(data.password)

        self.db.commit()
        return {"success": True, "message": "管理员更新成功"}

    def change_password(
        self, admin_id: int, old_password: str, new_password: str, current_admin_id: int
    ) -> dict:
        """修改管理员密码 — 校验旧密码"""
        if admin_id != current_admin_id:
            raise ForbiddenError("只能修改自己的密码")

        target = (
            self.db.query(Admin)
            .filter(Admin.id == admin_id, Admin.is_deleted == 0)
            .first()
        )
        if not target:
            raise NotFoundError("管理员不存在")

        if not verify_password(old_password, target.password_hash):
            raise ValidationError("旧密码错误")

        target.password_hash = hash_password(new_password)
        self.db.commit()
        return {"success": True, "message": "密码修改成功"}

    def get_permission_codes(self, admin: Admin) -> set[str]:
        if self.is_super_admin(admin):
            from backend.domain.admin.rbac_models import Permission

            return {
                p.code
                for p in self.db.query(Permission.code)
                .filter(Permission.is_deleted == 0)
                .all()
            }

        if not admin.admin_role_id:
            return set()

        from backend.domain.admin.rbac_models import RolePermission

        return {
            rp.permission_code
            for rp in self.db.query(RolePermission)
            .filter(
                RolePermission.role_id == admin.admin_role_id,
                RolePermission.is_deleted == 0,
            )
            .all()
        }

    def has_permission(self, admin: Admin, code: str) -> bool:
        return code in self.get_permission_codes(admin)

    def get_data_scope(self, admin: Admin) -> str:
        if self.is_super_admin(admin):
            return "all"
        if not admin.admin_role_id:
            return "none"
        if self.get_role_code(admin) == "teacher" and admin.teacher_id:
            return "own"
        return "all"

    def get_scoped_child_ids(self, admin: Admin) -> list[int] | None:
        scope = self.get_data_scope(admin)
        if scope == "all":
            return None
        if scope == "none":
            return []
        if scope == "own" and admin.teacher_id:
            from backend.domain.child.models import Child

            rows = (
                self.db.query(Child.id)
                .filter(
                    Child.teacher_id == admin.teacher_id,
                    Child.is_deleted == 0,
                )
                .all()
            )
            return [r[0] for r in rows]
        return []

    def delete_admin(self, admin_id: int, current_admin_id: int) -> dict:
        """删除管理员"""
        target = (
            self.db.query(Admin)
            .filter(Admin.id == admin_id, Admin.is_deleted == 0)
            .first()
        )
        if not target:
            raise NotFoundError("管理员不存在")

        # 不能删除自己
        if target.id == current_admin_id:
            raise ValidationError("不能删除当前登录的管理员")

        if self.is_super_admin(target):
            assert_not_last_super_admin(self.db, target.id)

        target.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "管理员已删除"}
