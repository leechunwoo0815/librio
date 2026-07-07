# backend/domain/admin/routers/admin_activities_router.py
"""活动管理路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.common.dependencies import get_db
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN, ROLE_STAFF
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    CreateActivityRequest,
    UpdateActivityRequest,
    BatchCheckinRequest,
)
from backend.domain.activity.service import ActivityService

router = APIRouter(prefix="/admin/api/activities", tags=["活动管理"])


@router.get("", response_model=list)
def list_activities(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取活动列表"""
    service = ActivityService(db)
    return service.list_activities()


@router.get("/{activity_id}", response_model=AdminActionResponse)
def get_activity(
    activity_id: int,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取活动详情"""
    service = ActivityService(db)
    result = service.get_activity(activity_id)
    # 返回字典格式
    return result.model_dump() if hasattr(result, 'model_dump') else result


@router.post("", response_model=AdminActionResponse, status_code=201)
def create_activity(
    data: CreateActivityRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """创建活动"""
    service = ActivityService(db)
    return service.create_activity(data)


@router.put("/{activity_id}", response_model=SuccessResponse)
def update_activity(
    activity_id: int,
    data: UpdateActivityRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """更新活动"""
    service = ActivityService(db)
    return service.update_activity(activity_id, data)


@router.delete("/{activity_id}", response_model=SuccessResponse)
def delete_activity(
    activity_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """删除活动"""
    service = ActivityService(db)
    return service.delete_activity(activity_id)


@router.get("/{activity_id}/enrollments", response_model=list)
def get_activity_enrollments(
    activity_id: int,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取活动报名列表"""
    service = ActivityService(db)
    return service.get_enrollments(activity_id)


@router.post("/{activity_id}/checkin", response_model=AdminActionResponse)
def batch_checkin(
    activity_id: int,
    data: BatchCheckinRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """批量签到"""
    service = ActivityService(db)
    return service.batch_checkin(activity_id, data.child_ids)
