# backend/domain/activity/router.py
"""活动域 API 路由"""

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_activity_service
from backend.domain.activity.schemas import (
    ActivityResponse,
    ActivityEnrollRequest,
    BatchCheckinRequest,
)
from backend.domain.activity.service import ActivityService
from backend.middleware.ownership import GetOwnedChildFromBody, GetOwnedEnrollment
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/activity", tags=["活动"])


@router.get("/", response_model=list[ActivityResponse])
def list_activities(
    service: ActivityService = Depends(get_activity_service),
    current_user=Depends(get_current_user),
):
    return service.list_activities()


@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(
    activity_id: int,
    service: ActivityService = Depends(get_activity_service),
    current_user=Depends(get_current_user),
):
    return service.get_activity(activity_id)


@router.post("/enroll", status_code=201)
def enroll(
    data: ActivityEnrollRequest,
    service: ActivityService = Depends(get_activity_service),
    child=Depends(GetOwnedChildFromBody()),
):
    return service.enroll(data)


@router.put("/enroll/{enrollment_id}/cancel")
def cancel_enrollment(
    service: ActivityService = Depends(get_activity_service),
    result=Depends(GetOwnedEnrollment()),
):
    _, enrollment = result
    return service.cancel_enrollment(enrollment.id)


@router.put("/enroll/{enrollment_id}/sign-in")
def sign_in(
    service: ActivityService = Depends(get_activity_service),
    result=Depends(GetOwnedEnrollment()),
):
    _, enrollment = result
    return service.sign_in(enrollment.id)


@router.get("/{activity_id}/enrollments")
def get_enrollments(
    activity_id: int,
    service: ActivityService = Depends(get_activity_service),
    current_user=Depends(get_current_user),
):
    """获取活动报名列表"""
    return service.get_enrollments(activity_id)


@router.post("/{activity_id}/checkin")
def batch_checkin(
    activity_id: int,
    data: BatchCheckinRequest,
    service: ActivityService = Depends(get_activity_service),
    current_user=Depends(get_current_user),
):
    """批量签到"""
    return service.batch_checkin(activity_id, data.child_ids)
