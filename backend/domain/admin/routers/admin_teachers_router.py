# backend/domain/admin/routers/admin_teachers_router.py
"""老师管理路由"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_admin_teacher_service
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    TeacherResponse,
    CreateTeacherRequest,
    UpdateTeacherRequest,
    AssignTeacherRequest,
    TeacherScheduleResponse,
    CreateScheduleRequest,
)
from backend.domain.admin.services.teacher_service import AdminTeacherService

router = APIRouter(prefix="/admin/api/teachers", tags=["老师管理"])


@router.get("", response_model=AdminActionResponse)
def list_teachers(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(get_current_admin),
):
    """获取老师列表"""
    return service.list_teachers(page, page_size)


@router.get("/{teacher_id}", response_model=TeacherResponse | None)
def get_teacher(
    teacher_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(get_current_admin),
):
    """获取老师详情"""
    return service.get_teacher_by_id(teacher_id)


@router.post("", response_model=TeacherResponse, status_code=201)
def create_teacher(
    data: CreateTeacherRequest,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    """创建老师"""
    return service.create_teacher(
        name=data.name,
        phone=data.phone,
        venue_id=data.venue_id,
        introduction=data.introduction,
        expertise=data.expertise,
    )


@router.put("/{teacher_id}", response_model=SuccessResponse)
def update_teacher(
    teacher_id: int,
    data: UpdateTeacherRequest,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    """更新老师"""
    return service.update_teacher(teacher_id, data)


@router.delete("/{teacher_id}", response_model=SuccessResponse)
def delete_teacher(
    teacher_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    """删除老师"""
    return service.delete_teacher(teacher_id)


@router.post("/assign", response_model=SuccessResponse)
def assign_teacher(
    data: AssignTeacherRequest,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    """分配老师给孩子"""
    return service.assign_teacher(data.child_id, data.teacher_id)


@router.get("/{teacher_id}/children", response_model=list)
def get_teacher_children(
    teacher_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(get_current_admin),
):
    """获取老师负责的孩子列表"""
    return service.get_teacher_children(teacher_id)


@router.get("/child/{child_id}", response_model=TeacherResponse | None)
def get_child_teacher(
    child_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(get_current_admin),
):
    """获取孩子的老师"""
    return service.get_child_teacher(child_id)


# ==================== 排班管理 ====================

@router.post("/schedule", response_model=TeacherScheduleResponse, status_code=201)
def create_schedule(
    data: CreateScheduleRequest,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(get_current_admin),
):
    """创建排班"""
    return service.create_schedule(data.teacher_id, data.weekday, data.start_time, data.end_time)


@router.get("/{teacher_id}/schedule", response_model=list[TeacherScheduleResponse])
def get_schedule(
    teacher_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(get_current_admin),
):
    """获取老师排班列表"""
    return service.get_teacher_schedule(teacher_id)


@router.delete("/schedule/{schedule_id}", response_model=SuccessResponse)
def delete_schedule(
    schedule_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(get_current_admin),
):
    """删除排班"""
    return service.delete_schedule(schedule_id)
