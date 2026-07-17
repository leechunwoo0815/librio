"""RBAC 权限控制模型 — Role / Permission / RolePermission"""

from sqlalchemy import BigInteger, Column, ForeignKey, String, Boolean, Integer, UniqueConstraint

from backend.common.base_model import BaseModel


class Role(BaseModel):
    __tablename__ = "role"
    __table_args__ = {"extend_existing": True}

    code = Column(String(32), unique=True, nullable=False, comment="角色代码: super_admin / staff / teacher")
    name = Column(String(50), nullable=False, comment="角色名称")
    description = Column(String(255), nullable=True, comment="角色描述")
    is_system = Column(Boolean, default=False, comment="系统内置不可删")
    sort_order = Column(Integer, default=0, comment="排序")


class Permission(BaseModel):
    __tablename__ = "permission"
    __table_args__ = {"extend_existing": True}

    code = Column(String(64), unique=True, nullable=False, comment="权限代码: group.action")
    name = Column(String(50), nullable=False, comment="权限名称")
    group_name = Column(String(32), nullable=False, comment="分组名称")
    description = Column(String(255), nullable=True, comment="权限描述")
    is_system = Column(Boolean, default=False, comment="系统内置不可删")
    sort_order = Column(Integer, default=0, comment="排序")


class RolePermission(BaseModel):
    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_code", name="uk_role_perm"),
        {"extend_existing": True},
    )

    role_id = Column(BigInteger, ForeignKey("role.id"), nullable=False, comment="角色ID")
    permission_code = Column(String(64), nullable=False, comment="权限代码")
