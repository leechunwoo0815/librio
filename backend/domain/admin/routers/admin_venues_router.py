# backend/domain/admin/routers/admin_venues_router.py
"""场馆管理路由"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_admin_venue_service
from backend.middleware.admin_rbac import require_perm
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    VenueResponse,
    CreateVenueRequest,
    UpdateVenueRequest,
)
from backend.domain.admin.services.venue_service import AdminVenueService

router = APIRouter(prefix="/admin/api/venues", tags=["场馆管理"])


@router.get("", response_model=AdminActionResponse)
def list_venues(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    service: AdminVenueService = Depends(get_admin_venue_service),
    admin=Depends(require_perm("venue.list")),
):
    """获取场馆列表"""
    return service.list_venues(page, page_size)


@router.post("", response_model=VenueResponse, status_code=201)
def create_venue(
    data: CreateVenueRequest,
    service: AdminVenueService = Depends(get_admin_venue_service),
    admin=Depends(require_perm("venue.create")),
):
    """创建场馆"""
    result = service.create_venue(data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="venue",
        operation="create",
        content=f"创建场馆: {data.name}",
    )
    return result


@router.put("/{venue_id}", response_model=SuccessResponse)
def update_venue(
    venue_id: int,
    data: UpdateVenueRequest,
    service: AdminVenueService = Depends(get_admin_venue_service),
    admin=Depends(require_perm("venue.edit")),
):
    """更新场馆"""
    result = service.update_venue(venue_id, data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="venue",
        operation="update",
        content=f"更新场馆 #{venue_id}",
    )
    return result


@router.delete("/{venue_id}", response_model=SuccessResponse)
def delete_venue(
    venue_id: int,
    service: AdminVenueService = Depends(get_admin_venue_service),
    admin=Depends(require_perm("venue.delete")),
):
    """删除场馆"""
    result = service.delete_venue(venue_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="venue",
        operation="delete",
        content=f"删除场馆 #{venue_id}",
    )
    return result
