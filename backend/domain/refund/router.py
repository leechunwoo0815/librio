# backend/domain/refund/router.py
"""退款域 API 路由"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from backend.common.dependencies import get_payment_gateway, get_refund_service
from backend.common.exceptions import ConflictError, NotFoundError
from backend.common.gateways.payment import PaymentGateway
from backend.middleware.admin_rbac import require_perm
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import GetOwnedRefund
from backend.domain.refund.schemas import RefundCreate, RefundAudit, RefundResponse
from backend.domain.refund.service import RefundService

router = APIRouter(prefix="/refund", tags=["退款"])


@router.post("/", response_model=RefundResponse, status_code=201)
def apply_refund(
    data: RefundCreate,
    service: RefundService = Depends(get_refund_service),
    current_user=Depends(get_current_user),
):
    return service.apply_refund(current_user.id, data)


@router.get("/")
def get_my_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RefundService = Depends(get_refund_service),
    current_user=Depends(get_current_user),
):
    return service.get_user_refunds(current_user.id, page, page_size)


@router.get("/{refund_id}", response_model=RefundResponse)
def get_refund_detail(
    refund_id: int,
    _ctx: tuple = Depends(GetOwnedRefund()),
):
    _, refund = _ctx
    return refund


@router.put("/{refund_id}/audit", response_model=RefundResponse)
def audit_refund(
    refund_id: int,
    audit: RefundAudit,
    background_tasks: BackgroundTasks,
    service: RefundService = Depends(get_refund_service),
    admin=Depends(require_perm("refund.audit")),
):
    audit.admin_id = admin.id
    result = service.audit_refund(refund_id, audit)

    if audit.status == 1:
        refund_order = service.get_refund_with_order(refund_id)
        if refund_order:
            refund, order = refund_order
            if refund and order:
                background_tasks.add_task(
                    RefundService._execute_wechat_refund,
                    refund.id,
                    order.order_no,
                    refund.refund_amount,
                    refund.review_comment or "",
                )

    return result


@router.post("/callback")
async def refund_callback(
    request: Request,
    service: RefundService = Depends(get_refund_service),
    payment_gateway: PaymentGateway = Depends(get_payment_gateway),
):
    """微信退款结果通知"""
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

    try:
        service.mark_refunded(callback_data.out_trade_no)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"code": "SUCCESS", "message": "退款处理完成"}
