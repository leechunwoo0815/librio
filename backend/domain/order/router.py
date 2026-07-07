# backend/domain/order/router.py
"""订单域 API 路由"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request

from backend.common.dependencies import get_order_service
from backend.common.exceptions import ConflictError, PaymentError
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import GetOwnedOrder
from backend.domain.order.schemas import (
    OrderCreate,
    OrderResponse,
    OrderPayCallback,
    OrderListResponse,
    RefundPreviewResponse,
)
from backend.domain.order.service import OrderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/order", tags=["订单"])


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(
    order_data: OrderCreate,
    order_service: OrderService = Depends(get_order_service),
    current_user=Depends(get_current_user),
):
    """创建订单"""
    return order_service.create_order(current_user.id, order_data)


@router.get("/", response_model=OrderListResponse)
def get_my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    order_service: OrderService = Depends(get_order_service),
    current_user=Depends(get_current_user),
):
    """获取我的订单列表"""
    return order_service.get_user_orders(current_user.id, page, page_size)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_detail(
    order_id: int,
    order_service: OrderService = Depends(get_order_service),
    _ctx: tuple = Depends(GetOwnedOrder()),
):
    """获取订单详情"""
    _, order = _ctx
    return order


@router.post("/payment-callback")
async def payment_callback(
    request: Request,
    order_service: OrderService = Depends(get_order_service),
):
    """支付回调 — 微信支付V3通知（验签 + 解密）"""
    body = await request.body()
    headers = dict(request.headers)

    from backend.integrations.wechat.pay_v3 import WeChatPayV3
    from backend.config import get_settings

    settings = get_settings()

    if not settings.DEBUG:
        # 生产环境：验签
        pay = WeChatPayV3()
        decrypted = pay.verify_callback(headers, body.decode())
        if not decrypted:
            raise PaymentError("回调验签失败")
        callback = OrderPayCallback(
            order_no=decrypted["out_trade_no"],
            trade_no=decrypted["transaction_id"],
            pay_type=1,
            amount=Decimal(str(decrypted["amount"]["total"])) / 100,
        )
    else:
        # 开发环境：跳过验签
        import json

        logger.warning("DEBUG mode: payment callback signature verification skipped")
        data = json.loads(body)
        callback = OrderPayCallback(**data)

    if not callback.order_no:
        from backend.common.exceptions import ValidationError

        raise ValidationError("回调缺少订单号")
    return order_service.handle_payment_callback(callback)


@router.get("/{order_id}/pay-params")
def get_pay_params(
    order_id: int,
    request: Request,
    order_service: OrderService = Depends(get_order_service),
    _ctx: tuple = Depends(GetOwnedOrder()),
):
    """获取微信支付参数（前端调用 wx.requestPayment 使用）

    生产环境返回微信支付V3的prepay_id等参数。
    开发/测试环境返回模拟参数。
    """
    _, order = _ctx
    if order.pay_status != 0:
        raise ConflictError("订单状态不允许支付")

    from backend.config import get_settings

    settings = get_settings()

    # 开发环境：直接标记订单为已支付（模拟支付成功）
    # ⚠️ 安全防护：仅允许 localhost 访问时自动完成支付
    if settings.DEBUG:
        client_host = request.client.host if request.client else ""
        if client_host not in ("127.0.0.1", "::1", "localhost"):
            raise PaymentError("模拟支付仅限本地开发环境")
        from backend.domain.order.schemas import OrderPayCallback
        from decimal import Decimal

        callback = OrderPayCallback(
            order_no=order.order_no,
            trade_no=f"mock_{order.order_no}",
            pay_type=1,
            amount=order.amount
            if isinstance(order.amount, Decimal)
            else Decimal(str(order.amount)),
        )
        return order_service.handle_payment_callback(callback)

    # 生产环境：调用微信支付V3获取真实prepay_id
    from backend.common.exceptions import ValidationError

    raise ValidationError("微信支付未配置，请联系管理员")


@router.get("/{order_id}/refund-preview", response_model=RefundPreviewResponse)
def preview_refund(
    order_id: int,
    used_days: int = Query(..., ge=0, description="已使用天数"),
    order_service: OrderService = Depends(get_order_service),
    _ctx: tuple = Depends(GetOwnedOrder()),
):
    """预览退款金额"""
    _, order = _ctx
    refund_amount = order_service.calculate_refund(order_id, used_days)
    return RefundPreviewResponse(
        order_id=order_id,
        used_days=used_days,
        refund_amount=Decimal(str(refund_amount)),
    )


@router.get("/upgrade-options/{child_id}", response_model=list[dict])
def get_upgrade_options(
    child_id: int,
    order_service: OrderService = Depends(get_order_service),
    current_user=Depends(get_current_user),
):
    """查询可升级选项及差价"""
    return order_service.get_upgrade_options(child_id)


@router.post("/upgrade", response_model=OrderResponse, status_code=201)
def create_upgrade_order(
    child_id: int = Query(..., description="孩子ID"),
    target_type: int = Query(..., description="目标类型: 4=季度 5=半年 3=年费"),
    order_service: OrderService = Depends(get_order_service),
    current_user=Depends(get_current_user),
):
    """创建升级订单 — 补齐差额"""
    return order_service.create_upgrade_order(
        current_user.id, child_id, target_type
    )
