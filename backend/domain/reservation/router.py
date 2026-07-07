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
from backend.middleware.admin_auth import require_role, ROLE_ADMIN, ROLE_STAFF
from backend.middleware.ownership import GetOwnedChild, GetOwnedChildFromBody

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
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
):
    return service.fulfill_reservation(data)


@router.get("/{child_id}", response_model=list[ReservationResponse])
def get_child_reservations(
    child=Depends(GetOwnedChild()),
    service: ReservationService = Depends(get_reservation_service),
):
    return service.get_child_reservations(child.id)
