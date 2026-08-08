# backend/domain/deposit/router.py
"""押金域 API 路由"""

import asyncio
import json

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
async def refund_deposit(
    data: DepositRefundRequest,
    service: DepositService = Depends(get_deposit_service),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    payment_gateway=Depends(get_payment_gateway),
):
    verify_child_ownership(data.child_id, current_user, db)
    result = service.refund_deposit(data)

    # E1：押金退款满足条件自动审核通过（申请时已强校验无未还书，罚款走B11抵扣）
    from backend.common.config_service import ConfigService

    if ConfigService.get_bool(db, "deposit_refund_auto_approve", True):
        result = await service.audit_refund(
            child_id=data.child_id,
            action="approve",
            admin_id=0,  # 0=系统自动审核
            payment_gateway=payment_gateway,
        )
    return result


@router.post("/partial-refund", response_model=DepositResponse)
async def partial_refund_deposit(
    data: DepositRefundRequest,
    service: DepositService = Depends(get_deposit_service),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    payment_gateway=Depends(get_payment_gateway),
):
    """A2：借满 N 本无逾期 → 减半退还押金（默认 600 元，一次为限）"""
    verify_child_ownership(data.child_id, current_user, db)
    return await service.partial_refund_deposit(data.child_id, payment_gateway)


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


@router.post("/pay-fines")
async def pay_fines(
    data: DepositRefundRequest,
    service: DepositService = Depends(get_deposit_service),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    payment_gateway=Depends(get_payment_gateway),
):
    """B12：线上缴纳罚款（微信支付，缴清后 outstanding_fines 归零）"""
    verify_child_ownership(data.child_id, current_user, db)
    return await service.pay_fines(data, payment_gateway, current_user)


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

    valid = await payment_gateway.verify_callback_signature(
        body_str, signature, timestamp, nonce
    )
    if not valid:
        raise HTTPException(status_code=400, detail="签名验证失败")

    encrypted = json.loads(body_str).get("resource", {})
    callback_data = await payment_gateway.decrypt_callback_data(
        ciphertext=encrypted.get("ciphertext", ""),
        nonce=encrypted.get("nonce", ""),
        associated_data=encrypted.get("associated_data", ""),
    )

    # 网关 decrypt_callback_data 已做分→元转换，直接使用
    callback_amount = callback_data.amount
    # F-048：trade_state 消费——非 SUCCESS 不确认押金到账（对齐订单 F75-③）
    if callback_data.trade_state and callback_data.trade_state != "SUCCESS":
        import logging

        logging.getLogger(__name__).warning(
            f"Deposit callback non-SUCCESS: trade_state={callback_data.trade_state}"
        )
        return {"success": True, "deposit": {"ignored": True}}

    # B12：先尝试罚款缴款单（FINE 前缀单号），命中则核销罚款
    if callback_data.out_trade_no.startswith("FINE"):
        settled = await asyncio.to_thread(
            service.handle_fine_callback, callback_data.out_trade_no
        )
        if settled:
            return {"success": True, "fine_payment": True}

    result = await asyncio.to_thread(
        service.handle_callback, callback_data.out_trade_no, callback_amount
    )
    return {"success": True, "deposit": {"id": result.id, "status": result.status}}
