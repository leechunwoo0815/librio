# backend/domain/admin/routers/admin_activities_router.py
"""活动管理路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import get_db
from backend.middleware.admin_rbac import require_perm
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    CreateActivityRequest,
    UpdateActivityRequest,
    BatchCheckinRequest,
)
from backend.domain.activity.service import ActivityService

router = APIRouter(prefix="/admin/api/activities", tags=["活动管理"])


@router.get("", response_model=AdminActionResponse)
def list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("activity.list")),
    db: Session = Depends(get_db),
):
    """获取活动列表（分页）"""
    service = ActivityService(db)
    return service.list_with_count(page=page, page_size=page_size)


@router.get("/{activity_id}", response_model=AdminActionResponse)
def get_activity(
    activity_id: int,
    admin=Depends(require_perm("activity.view")),
    db: Session = Depends(get_db),
):
    """获取活动详情"""
    service = ActivityService(db)
    result = service.get_activity(activity_id)
    # 返回字典格式
    return result.model_dump() if hasattr(result, "model_dump") else result


@router.post("", response_model=AdminActionResponse, status_code=201)
def create_activity(
    data: CreateActivityRequest,
    admin=Depends(require_perm("activity.create")),
    db: Session = Depends(get_db),
):
    """创建活动"""
    service = ActivityService(db)
    result = service.create_activity(data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="activity",
        operation="create",
        content=f"创建活动: {data.title}",
    )
    return result


@router.put("/{activity_id}", response_model=SuccessResponse)
def update_activity(
    activity_id: int,
    data: UpdateActivityRequest,
    admin=Depends(require_perm("activity.edit")),
    db: Session = Depends(get_db),
):
    """更新活动"""
    service = ActivityService(db)
    result = service.update_activity(activity_id, data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="activity",
        operation="update",
        content=f"更新活动 #{activity_id}",
    )
    return result


@router.delete("/{activity_id}", response_model=SuccessResponse)
def delete_activity(
    activity_id: int,
    admin=Depends(require_perm("activity.delete")),
    db: Session = Depends(get_db),
):
    """删除活动"""
    service = ActivityService(db)
    result = service.delete_activity(activity_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="activity",
        operation="delete",
        content=f"删除活动 #{activity_id}",
    )
    return result


@router.put("/{activity_id}/cancel", response_model=AdminActionResponse)
def cancel_activity(
    activity_id: int,
    admin=Depends(require_perm("activity.cancel")),
    db: Session = Depends(get_db),
):
    """取消活动"""
    service = ActivityService(db)
    result = service.cancel_activity(activity_id, admin.id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="activity",
        operation="cancel",
        content=f"取消活动 #{activity_id}",
    )
    return result


@router.get("/{activity_id}/enrollments", response_model=list)
def get_activity_enrollments(
    activity_id: int,
    admin=Depends(require_perm("activity.enrollment")),
    db: Session = Depends(get_db),
):
    """获取活动报名列表"""
    service = ActivityService(db)
    return service.get_enrollments(activity_id)


@router.post("/{activity_id}/checkin", response_model=AdminActionResponse)
def batch_checkin(
    activity_id: int,
    data: BatchCheckinRequest,
    admin=Depends(require_perm("activity.checkin")),
    db: Session = Depends(get_db),
):
    """批量签到"""
    service = ActivityService(db)
    result = service.batch_checkin(activity_id, data.child_ids)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="activity",
        operation="batch_checkin",
        content=f"批量签到: 活动 #{activity_id}",
    )
    return result


@router.put("/enroll/{enrollment_id}/sign-in", response_model=AdminActionResponse)
def admin_sign_in(
    enrollment_id: int,
    admin=Depends(require_perm("activity.checkin")),
    db: Session = Depends(get_db),
):
    """管理员签到 — 通过报名记录ID签到"""
    service = ActivityService(db)
    enrollment = service.get_enrollment_by_id(enrollment_id)
    result = service.sign_in(enrollment.id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="activity",
        operation="sign_in",
        content=f"管理员签到: 报名 #{enrollment_id}",
    )
    return result
