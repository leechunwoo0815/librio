# backend/domain/deposit/router.py
"""押金域 API 路由"""

import asyncio
import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.common.dependencies import get_deposit_service, get_payment_gateway
from backend.common.gateways.payment import PaymentGateway
from backend.domain.deposit.schemas import (
    DepositPayRequest,
    DepositRefundRequest,
    DepositDeductRequest,
    DepositPayResponse,
    DepositResponse,
)
from backend.domain.deposit.service import DepositService
from backend.middleware.admin_rbac import require_perm
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import verify_child_ownership, GetOwnedChildFromQuery
from backend.database import get_db

router = APIRouter(prefix="/deposit", tags=["押金"])


@router.post("/pay", response_model=DepositPayResponse, status_code=201)
async def pay_deposit(
    data: DepositPayRequest,
    service: DepositService = Depends(get_deposit_service),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    payment_gateway=Depends(get_payment_gateway),
):
    verify_child_ownership(data.child_id, current_user, db)
    return await service.pay_deposit(data, payment_gateway, current_user)


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
    admin=Depends(require_perm("deposit.deduct")),
):
    return service.deduct_deposit(data)


@router.get("/status")
def get_deposit_status(
    child=Depends(GetOwnedChildFromQuery()),
    service: DepositService = Depends(get_deposit_service),
):
    """查询押金状态"""
    return service.get_deposit_status(child.id)


@router.post("/repay", response_model=DepositPayResponse, status_code=201)
async def repay_deposit(
    child=Depends(GetOwnedChildFromQuery()),
    service: DepositService = Depends(get_deposit_service),
    current_user=Depends(get_current_user),
    payment_gateway=Depends(get_payment_gateway),
):
    """重新缴纳押金"""
    return await service.repay_deposit(child.id, payment_gateway, current_user)


@router.post("/callback")
async def deposit_callback(
    request: Request,
    service: DepositService = Depends(get_deposit_service),
    payment_gateway: PaymentGateway = Depends(get_payment_gateway),
):
    """押金支付回调 — 接收微信支付 V3 加密通知"""
    body = await request.body()
    body_str = body.decode()

    signature = request.headers.get("wechatpay-signature", "")
    timestamp = request.headers.get("wechatpay-timestamp", "")
    nonce = request.headers.get("wechatpay-nonce", "")

    valid = await payment_gateway.verify_callback_signature(body_str, signature, timestamp, nonce)
    if not valid:
        raise HTTPException(status_code=400, detail="签名验证失败")

    encrypted = json.loads(body_str).get("resource", {})
    callback_data = await payment_gateway.decrypt_callback_data(
        ciphertext=encrypted.get("ciphertext", ""),
        nonce=encrypted.get("nonce", ""),
        associated_data=encrypted.get("associated_data", ""),
    )

    callback_amount = (Decimal(str(callback_data.amount)) / Decimal("100")) if callback_data.amount is not None else None
    result = await asyncio.to_thread(service.handle_callback, callback_data.out_trade_no, callback_amount)
    return {"success": True, "deposit": {"id": result.id, "status": result.status}}
