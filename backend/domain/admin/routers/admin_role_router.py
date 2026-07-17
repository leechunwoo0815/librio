# backend/domain/admin/routers/admin_role_router.py
"""角色管理路由 — RBAC 角色的 CRUD 与权限分配。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.common.dependencies import get_db
from backend.domain.admin.services.role_service import AdminRoleService
from backend.domain.admin.admin_schemas import AdminActionResponse, SuccessResponse
from backend.middleware.admin_rbac import require_perm

router = APIRouter(prefix="/admin/api", tags=["角色管理"])


def get_admin_role_service(db: Session = Depends(get_db)) -> AdminRoleService:
    return AdminRoleService(db)


class CreateRoleRequest(BaseModel):
    model_config = {"extra": "forbid"}
    code: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    sort_order: int = 0


class UpdateRoleRequest(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(None, max_length=50)
    description: str | None = None
    sort_order: int | None = None


class SetPermissionsRequest(BaseModel):
    model_config = {"extra": "forbid"}
    permission_codes: list[str] = Field(..., description="权限代码列表")


@router.get("/roles", response_model=AdminActionResponse)
def list_roles(
    service: AdminRoleService = Depends(get_admin_role_service),
    admin=Depends(require_perm("role.list")),
):
    """获取角色列表"""
    return service.list_roles()


@router.get("/roles/{role_id}", response_model=AdminActionResponse)
def get_role(
    role_id: int,
    service: AdminRoleService = Depends(get_admin_role_service),
    admin=Depends(require_perm("role.list")),
):
    """获取角色详情（含权限列表）"""
    return service.get_role(role_id)


@router.get("/roles/{role_id}/permissions", response_model=AdminActionResponse)
def get_role_permissions(
    role_id: int,
    service: AdminRoleService = Depends(get_admin_role_service),
    admin=Depends(require_perm("role.list")),
):
    """获取角色的权限树（所有权限分组 + 已分配标识）"""
    return service.get_all_permissions(role_id)


@router.put("/roles/{role_id}/permissions", response_model=SuccessResponse)
def set_role_permissions(
    role_id: int,
    data: SetPermissionsRequest,
    service: AdminRoleService = Depends(get_admin_role_service),
    admin=Depends(require_perm("role.edit")),
):
    """设置角色权限（全量替换）"""
    result = service.set_role_permissions(role_id, data.permission_codes)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="role",
        operation="update_permissions",
        content=f"更新角色 #{role_id} 权限: {len(data.permission_codes)} 个",
    )
    return result


@router.post("/roles", status_code=201, response_model=AdminActionResponse)
def create_role(
    data: CreateRoleRequest,
    service: AdminRoleService = Depends(get_admin_role_service),
    admin=Depends(require_perm("role.edit")),
):
    """创建自定义角色"""
    result = service.create_role(data.code, data.name, data.description, data.sort_order)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="role",
        operation="create",
        content=f"创建角色: {data.code} ({data.name})",
    )
    return result


@router.put("/roles/{role_id}", response_model=SuccessResponse)
def update_role(
    role_id: int,
    data: UpdateRoleRequest,
    service: AdminRoleService = Depends(get_admin_role_service),
    admin=Depends(require_perm("role.edit")),
):
    """更新角色基本信息"""
    result = service.update_role(role_id, data.name, data.description, data.sort_order)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="role",
        operation="update",
        content=f"更新角色 #{role_id}",
    )
    return result


@router.delete("/roles/{role_id}", response_model=SuccessResponse)
def delete_role(
    role_id: int,
    service: AdminRoleService = Depends(get_admin_role_service),
    admin=Depends(require_perm("role.edit")),
):
    """删除角色（系统角色不可删除）"""
    result = service.delete_role(role_id)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="role",
        operation="delete",
        content=f"删除角色 #{role_id}",
    )
    return result
