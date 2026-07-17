# backend/domain/parent_course_time/router.py
"""亲子课时间段 API 路由"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_db
from backend.middleware.admin_rbac import require_perm
from backend.middleware.auth import get_current_user
from backend.domain.parent_course_time.schemas import (
    ParentCourseTimeCreate,
    ParentCourseTimeResponse,
    ParentCourseTimeUpdate,
)
from backend.domain.parent_course_time.service import ParentCourseTimeService

router = APIRouter(prefix="/parent-course-time", tags=["亲子课时间"])


# ============================================================
# 用户端
# ============================================================


@router.get("/venue/{venue_id}", response_model=list[ParentCourseTimeResponse])
def list_slots(
    venue_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """用户查看场馆可选时间段"""
    service = ParentCourseTimeService(db)
    return service.list_by_venue(venue_id)


# ============================================================
# 管理端
# ============================================================


@router.get("/admin", response_model=list[ParentCourseTimeResponse])
def admin_list_slots(
    venue_id: int | None = Query(None, description="按场馆筛选"),
    db=Depends(get_db),
    admin=Depends(require_perm("parent_course_time.list")),
):
    """管理员查看所有时间段"""
    service = ParentCourseTimeService(db)
    return service.list_all(venue_id)


@router.post("/admin", response_model=ParentCourseTimeResponse, status_code=201)
def admin_create_slot(
    data: ParentCourseTimeCreate,
    db=Depends(get_db),
    admin=Depends(require_perm("parent_course_time.create")),
):
    """管理员创建时间段"""
    service = ParentCourseTimeService(db)
    return service.create(data)


@router.put("/admin/{slot_id}", response_model=ParentCourseTimeResponse)
def admin_update_slot(
    slot_id: int,
    data: ParentCourseTimeUpdate,
    db=Depends(get_db),
    admin=Depends(require_perm("parent_course_time.edit")),
):
    """管理员更新时间段"""
    service = ParentCourseTimeService(db)
    return service.update(slot_id, data)


@router.delete("/admin/{slot_id}", response_model=dict)
def admin_delete_slot(
    slot_id: int,
    db=Depends(get_db),
    admin=Depends(require_perm("parent_course_time.delete")),
):
    """管理员删除时间段（软删除）"""
    service = ParentCourseTimeService(db)
    return service.delete(slot_id)
