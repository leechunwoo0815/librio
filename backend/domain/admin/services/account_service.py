# backend/domain/admin/services/account_service.py
"""管理端账号 Service — 从 AdminService 拆分出来的独立域服务。"""

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.common.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.domain.admin.models import Admin


class AdminAccountService:
    """管理员账号：认证、CRUD。"""

    def __init__(self, db: Session):
        self.db = db

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
        if not admin or not admin.verify_password(password):
            return None
        return admin

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
            "role_name": "超级管理员" if target.role == 0 else "员工",
            "phone": target.phone,
            "status": target.status,
            "last_login": target.last_login.isoformat()
            if hasattr(target, "last_login") and target.last_login
            else None,
            "create_time": target.create_time.isoformat() if target.create_time else None,
        }

    def create_admin(self, data, current_admin_id: int) -> dict:
        """创建管理员"""
        existing = self.db.query(Admin).filter(Admin.username == data.username).first()
        if existing:
            raise ValidationError("用户名已存在")

        new_admin = Admin(
            username=data.username,
            name=data.name or data.username,
            role=data.role,
            status=1,
        )
        new_admin.set_password(data.password)
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
            "message": "管理员创建成功",
        }

    def update_admin(self, admin_id: int, data, current_admin_id: int) -> dict:
        """更新管理员"""
        target = (
            self.db.query(Admin)
            .filter(Admin.id == admin_id, Admin.is_deleted == 0)
            .first()
        )
        if not target:
            raise NotFoundError("管理员不存在")

        # 禁止修改自己
        if target.id == current_admin_id:
            raise ForbiddenError("不能修改自己的信息")

        # 禁止将其他人提升为比自己更高的角色
        current = self.db.query(Admin).filter(Admin.id == current_admin_id).first()
        if data.role is not None and current and data.role < current.role:
            raise ForbiddenError("不能将其他人提升为比自己更高的角色")

        update_data = data.model_dump(exclude_unset=True)
        allowed_fields = ["name", "role", "status", "phone"]
        for key, value in update_data.items():
            if key in allowed_fields:
                setattr(target, key, value)

        if data.password:
            target.set_password(data.password)

        self.db.commit()
        return {"success": True, "message": "管理员更新成功"}

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

        target.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "管理员已删除"}
