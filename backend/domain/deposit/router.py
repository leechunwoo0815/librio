# backend/domain/deposit/router.py
"""押金域 API 路由"""

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_deposit_service
from backend.domain.deposit.schemas import (
    DepositPayRequest,
    DepositRefundRequest,
    DepositDeductRequest,
    DepositResponse,
)
from backend.domain.deposit.service import DepositService
from backend.middleware.admin_auth import require_role, ROLE_ADMIN
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import verify_child_ownership, GetOwnedChildFromQuery
from backend.database import get_db

router = APIRouter(prefix="/deposit", tags=["押金"])


@router.post("/pay", response_model=DepositResponse, status_code=201)
def pay_deposit(
    data: DepositPayRequest,
    service: DepositService = Depends(get_deposit_service),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    verify_child_ownership(data.child_id, current_user, db)
    return service.pay_deposit(data)


@router.post("/refund", response_model=DepositResponse)
def refund_deposit(
    data: DepositRefundRequest,
    service: DepositService = Depends(get_deposit_service),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    verify_child_ownership(data.child_id, current_user, db)
    return service.refund_deposit(data)


@router.post("/deduct", response_model=DepositResponse)
def deduct_deposit(
    data: DepositDeductRequest,
    service: DepositService = Depends(get_deposit_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    return service.deduct_deposit(data)


@router.get("/status")
def get_deposit_status(
    child=Depends(GetOwnedChildFromQuery()),
    service: DepositService = Depends(get_deposit_service),
):
    """查询押金状态"""
    return service.get_deposit_status(child.id)


@router.post("/repay", response_model=DepositResponse, status_code=201)
def repay_deposit(
    child=Depends(GetOwnedChildFromQuery()),
    service: DepositService = Depends(get_deposit_service),
):
    """重新缴纳押金"""
    return service.repay_deposit(child.id)
