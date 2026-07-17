# backend/domain/admin/routers/admin_teachers_router.py
"""老师管理路由"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_admin_teacher_service
from backend.middleware.admin_rbac import require_perm
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
    admin=Depends(require_perm("teacher.list")),
):
    """获取老师列表"""
    return service.list_teachers(page, page_size)


@router.get("/{teacher_id}", response_model=TeacherResponse | None)
def get_teacher(
    teacher_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.view")),
):
    """获取老师详情"""
    return service.get_teacher_by_id(teacher_id)


@router.post("", response_model=TeacherResponse, status_code=201)
def create_teacher(
    data: CreateTeacherRequest,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.create")),
):
    """创建老师"""
    result = service.create_teacher(
        name=data.name,
        phone=data.phone,
        venue_id=data.venue_id,
        english_name=data.english_name,
        title=data.title,
        introduction=data.introduction,
        expertise=data.expertise,
        status=data.status,
    )
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="teacher",
        operation="create",
        content=f"创建老师: {data.name}",
    )
    return result


@router.put("/{teacher_id}", response_model=SuccessResponse)
def update_teacher(
    teacher_id: int,
    data: UpdateTeacherRequest,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.edit")),
):
    """更新老师"""
    result = service.update_teacher(teacher_id, data)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="teacher",
        operation="update",
        content=f"更新老师 #{teacher_id}",
    )
    return result


@router.delete("/{teacher_id}", response_model=SuccessResponse)
def delete_teacher(
    teacher_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.delete")),
):
    """删除老师"""
    result = service.delete_teacher(teacher_id)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="teacher",
        operation="delete",
        content=f"删除老师 #{teacher_id}",
    )
    return result


@router.post("/assign", response_model=SuccessResponse)
def assign_teacher(
    data: AssignTeacherRequest,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.assign")),
):
    """分配老师给孩子"""
    result = service.assign_teacher(data.child_id, data.teacher_id)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="teacher",
        operation="assign",
        content=f"分配老师 #{data.teacher_id} 给孩子 #{data.child_id}",
    )
    return result


@router.get("/{teacher_id}/children", response_model=list)
def get_teacher_children(
    teacher_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.view")),
):
    """获取老师负责的孩子列表"""
    return service.get_teacher_children(teacher_id)


@router.get("/child/{child_id}", response_model=TeacherResponse | None)
def get_child_teacher(
    child_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.view")),
):
    """获取孩子的老师"""
    return service.get_child_teacher(child_id)


# ==================== 排班管理 ====================

@router.post("/schedule", response_model=TeacherScheduleResponse, status_code=201)
def create_schedule(
    data: CreateScheduleRequest,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.schedule")),
):
    """创建排班"""
    result = service.create_schedule(data.teacher_id, data.weekday, data.start_time, data.end_time)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="teacher_schedule",
        operation="create",
        content=f"创建排班: teacher #{data.teacher_id}, weekday {data.weekday}",
    )
    return result


@router.get("/{teacher_id}/schedule", response_model=list[TeacherScheduleResponse])
def get_schedule(
    teacher_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.schedule")),
):
    """获取老师排班列表"""
    return service.get_teacher_schedule(teacher_id)


@router.delete("/schedule/{schedule_id}", response_model=SuccessResponse)
def delete_schedule(
    schedule_id: int,
    service: AdminTeacherService = Depends(get_admin_teacher_service),
    admin=Depends(require_perm("teacher.schedule")),
):
    """删除排班"""
    result = service.delete_schedule(schedule_id)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="teacher_schedule",
        operation="delete",
        content=f"删除排班 #{schedule_id}",
    )
    return result
