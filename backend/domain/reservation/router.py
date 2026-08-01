# backend/domain/reservation/router.py
"""预约域 API 路由"""

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_reservation_service
from backend.domain.reservation.schemas import (
    ReservationCreateRequest,
    ReservationFulfillRequest,
    ReservationResponse,
)
from backend.domain.reservation.service import ReservationService
from backend.middleware.admin_rbac import require_perm
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import GetOwnedChild, GetOwnedChildFromBody
from backend.domain.user.schemas import UserResponse

router = APIRouter(prefix="/reservation", tags=["预约"])


@router.post("/", response_model=ReservationResponse, status_code=201)
def create_reservation(
    data: ReservationCreateRequest,
    service: ReservationService = Depends(get_reservation_service),
    child=Depends(GetOwnedChildFromBody()),
):
    return service.create_reservation(data)


@router.post("/fulfill", response_model=ReservationResponse)
def fulfill_reservation(
    data: ReservationFulfillRequest,
    service: ReservationService = Depends(get_reservation_service),
    admin=Depends(require_perm("reservation.fulfill")),
):
    return service.fulfill_reservation(data)


@router.get("/{child_id}", response_model=list[ReservationResponse])
def get_child_reservations(
    child=Depends(GetOwnedChild()),
    service: ReservationService = Depends(get_reservation_service),
):
    return service.get_child_reservations(child.id)


@router.post("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    service: ReservationService = Depends(get_reservation_service),
    current_user: UserResponse = Depends(get_current_user),
):
    return service.cancel_reservation(reservation_id, user_id=current_user.id)


# ==================== F4 等候名单 ====================


@router.post("/waitlist/join", status_code=201)
def join_waitlist(
    data: ReservationCreateRequest,
    service: ReservationService = Depends(get_reservation_service),
    child=Depends(GetOwnedChildFromBody()),
):
    """F4：库存为 0 时加入等候名单（到货/释放自动通知，先到先得）"""
    return service.join_waitlist(child.id, data.book_id)


@router.get("/waitlist/{child_id}")
def get_child_waitlist(
    child=Depends(GetOwnedChild()),
    service: ReservationService = Depends(get_reservation_service),
):
    """孩子的活跃等候名单"""
    return service.get_child_waitlist(child.id)


@router.post("/waitlist/{waitlist_id}/cancel")
def cancel_waitlist(
    waitlist_id: int,
    service: ReservationService = Depends(get_reservation_service),
    current_user: UserResponse = Depends(get_current_user),
):
    """取消等候"""
    return service.cancel_waitlist(waitlist_id, user_id=current_user.id)
