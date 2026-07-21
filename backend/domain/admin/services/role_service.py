"""管理端角色管理 Service — RBAC 角色的 CRUD 与权限分配。"""

from sqlalchemy.orm import Session

from backend.common.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.domain.admin.rbac_models import Role, Permission, RolePermission


class AdminRoleService:
    """角色管理：列表、详情、权限分配。"""

    def __init__(self, db: Session):
        self.db = db

    def list_roles(self) -> dict:
        roles = (
            self.db.query(Role)
            .filter(Role.is_deleted == 0)
            .order_by(Role.sort_order)
            .all()
        )
        from sqlalchemy import func

        result = []
        for r in roles:
            count = (
                self.db.query(func.count(RolePermission.id))
                .filter(
                    RolePermission.role_id == r.id,
                    RolePermission.is_deleted == 0,
                )
                .scalar()
                or 0
            )
            result.append(
                {
                    "id": r.id,
                    "code": r.code,
                    "name": r.name,
                    "description": r.description,
                    "is_system": r.is_system,
                    "sort_order": r.sort_order,
                    "permission_count": count,
                }
            )
        return {"items": result, "total": len(result)}

    def get_role(self, role_id: int) -> dict:
        role = (
            self.db.query(Role).filter(Role.id == role_id, Role.is_deleted == 0).first()
        )
        if not role:
            raise NotFoundError("角色不存在")

        perm_codes = {
            rp.permission_code
            for rp in self.db.query(RolePermission)
            .filter(
                RolePermission.role_id == role_id,
                RolePermission.is_deleted == 0,
            )
            .all()
        }
        return {
            "id": role.id,
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "sort_order": role.sort_order,
            "permission_codes": sorted(perm_codes),
        }

    def get_all_permissions(self, role_id: int | None = None) -> dict:
        perms = (
            self.db.query(Permission)
            .filter(Permission.is_deleted == 0)
            .order_by(Permission.group_name, Permission.sort_order)
            .all()
        )

        assigned = set()
        if role_id:
            role = (
                self.db.query(Role)
                .filter(Role.id == role_id, Role.is_deleted == 0)
                .first()
            )
            if not role:
                raise NotFoundError("角色不存在")
            if role.code == "super_admin":
                assigned = {p.code for p in perms}
            else:
                assigned = {
                    rp.permission_code
                    for rp in self.db.query(RolePermission)
                    .filter(
                        RolePermission.role_id == role_id,
                        RolePermission.is_deleted == 0,
                    )
                    .all()
                }

        groups = {}
        for p in perms:
            g = p.group_name
            if g not in groups:
                groups[g] = []
            groups[g].append(
                {
                    "code": p.code,
                    "name": p.name,
                    "description": p.description,
                    "is_assigned": p.code in assigned,
                }
            )
        return {
            "groups": [
                {"group_name": g, "permissions": items} for g, items in groups.items()
            ],
            "total": len(perms),
        }

    def set_role_permissions(self, role_id: int, permission_codes: list[str]) -> dict:
        role = (
            self.db.query(Role).filter(Role.id == role_id, Role.is_deleted == 0).first()
        )
        if not role:
            raise NotFoundError("角色不存在")
        self.db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
        ).update({"is_deleted": 1}, synchronize_session=False)
        self.db.flush()

        for code in permission_codes:
            perm = (
                self.db.query(Permission)
                .filter(Permission.code == code, Permission.is_deleted == 0)
                .first()
            )
            if perm:
                existing = (
                    self.db.query(RolePermission)
                    .filter(
                        RolePermission.role_id == role_id,
                        RolePermission.permission_code == code,
                    )
                    .first()
                )
                if existing:
                    if existing.is_deleted:
                        existing.is_deleted = 0
                        self.db.flush()
                else:
                    self.db.add(RolePermission(role_id=role_id, permission_code=code))
                    self.db.flush()

        self.db.commit()
        return {"success": True, "message": "角色权限更新成功"}

    def create_role(
        self, code: str, name: str, description: str | None = None, sort_order: int = 0
    ) -> dict:
        existing = (
            self.db.query(Role).filter(Role.code == code, Role.is_deleted == 0).first()
        )
        if existing:
            raise ValidationError("角色代码已存在")

        role = Role(
            code=code,
            name=name,
            description=description,
            is_system=False,
            sort_order=sort_order,
        )
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return {
            "id": role.id,
            "code": role.code,
            "name": role.name,
            "message": "角色创建成功",
        }

    def update_role(
        self,
        role_id: int,
        name: str | None = None,
        description: str | None = None,
        sort_order: int | None = None,
    ) -> dict:
        role = (
            self.db.query(Role).filter(Role.id == role_id, Role.is_deleted == 0).first()
        )
        if not role:
            raise NotFoundError("角色不存在")

        if role.is_system and name is not None and role.name != name:
            raise ForbiddenError("系统内置角色不可改名")

        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        if sort_order is not None:
            role.sort_order = sort_order
        self.db.commit()
        return {"success": True, "message": "角色更新成功"}

    def delete_role(self, role_id: int) -> dict:
        role = (
            self.db.query(Role).filter(Role.id == role_id, Role.is_deleted == 0).first()
        )
        if not role:
            raise NotFoundError("角色不存在")
        if role.is_system:
            raise ForbiddenError("系统内置角色不可删除")

        from backend.domain.admin.models import Admin

        admin_count = (
            self.db.query(Admin)
            .filter(Admin.admin_role_id == role_id, Admin.is_deleted == 0)
            .count()
        )
        if admin_count > 0:
            raise ValidationError(f"该角色下还有 {admin_count} 名管理员，无法删除")

        role.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "角色已删除"}
