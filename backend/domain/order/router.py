# backend/domain/order/router.py
"""订单域 API 路由"""

import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.common.dependencies import get_order_service
from backend.common.exceptions import ConflictError, PaymentError, ValidationError
from backend.database import get_db
from backend.domain.user.repository import UserRepository
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import GetOwnedOrder
from backend.common.types import OrderType
from backend.domain.order.schemas import (
    OrderCreate,
    OrderResponse,
    OrderPayCallback,
    OrderListResponse,
    ProductTiersResponse,
    RefundPreviewResponse,
    TierInfo,
    TierFeature,
)
from backend.domain.order.service import OrderService
from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/order", tags=["订单"])


@router.get("/tiers", response_model=ProductTiersResponse)
def get_product_tiers(
    order_service: OrderService = Depends(get_order_service),
):
    tiers = [
        TierInfo(
            type=1, name="亲子课", price=order_service.get_price_for_type(OrderType.PARENT_COURSE), unit="次",
            original_price=order_service.get_original_price(OrderType.PARENT_COURSE), discount_tag="限时特惠", sort_order=1,
            features=[
                TierFeature(icon="👩‍👧", title="亲子共读", desc="专业老师指导亲子共读"),
                TierFeature(icon="📚", title="精选绘本", desc="适龄英文原版绘本"),
                TierFeature(icon="🎯", title="阅读指导", desc="个性化阅读建议"),
                TierFeature(icon="📊", title="成长记录", desc="记录每次阅读成长"),
            ],
            cta="立即报名",
        ),
        TierInfo(
            type=2, name="观察期", price=order_service.get_price_for_type(OrderType.OBSERVATION), unit="30天",
            original_price=None, discount_tag=None, sort_order=2,
            features=[
                TierFeature(icon="📚", title="在线阅读全量图书", desc="A-Z 全级别 3,500+ 英文原版图书"),
                TierFeature(icon="✅", title="每日阅读打卡", desc="培养孩子坚持阅读的好习惯"),
                TierFeature(icon="📊", title="阅读数据统计", desc="实时追踪阅读时长、词汇量、进度"),
                TierFeature(icon="👩‍🏫", title="老师定期评估", desc="专业老师每周阅读能力评估与反馈"),
                TierFeature(icon="📋", title="观察期结束报告", desc="30天后生成个性化阅读能力分析报告"),
            ],
            cta="立即报名",
        ),
        TierInfo(
            type=3, name="正式会员", price=order_service.get_price_for_type(OrderType.OFFICIAL_MEMBER), unit="年",
            original_price=order_service.get_original_price(OrderType.OFFICIAL_MEMBER), discount_tag="限时特惠", sort_order=3,
            features=[
                TierFeature(icon="📚", title="全量图书无限阅读", desc="平台所有图书随时在线阅读"),
                TierFeature(icon="🎯", title="A-Z 26级晋级体系", desc="科学分级，循序渐进提升阅读能力"),
                TierFeature(icon="🏆", title="排行榜竞技", desc="与同龄小伙伴比拼阅读量"),
                TierFeature(icon="📜", title="晋级证书", desc="每通过一级获得专属晋级证书"),
                TierFeature(icon="⭐", title="成就系统", desc="丰富的成就徽章记录每个里程碑"),
            ],
            cta="立即开通",
        ),
        TierInfo(
            type=5, name="半年会员", price=order_service.get_price_for_type(OrderType.SEMI_ANNUAL), unit="半年",
            original_price=None, discount_tag=None, sort_order=4,
            features=[
                TierFeature(icon="📚", title="全量图书无限阅读", desc="平台所有图书随时在线阅读"),
                TierFeature(icon="🎯", title="A-Z 26级晋级体系", desc="科学分级，循序渐进提升阅读能力"),
                TierFeature(icon="🏆", title="排行榜竞技", desc="与同龄小伙伴比拼阅读量"),
                TierFeature(icon="📜", title="晋级证书", desc="每通过一级获得专属晋级证书"),
                TierFeature(icon="⭐", title="成就系统", desc="丰富的成就徽章记录每个里程碑"),
            ],
            cta="立即开通",
        ),
        TierInfo(
            type=4, name="季度会员", price=order_service.get_price_for_type(OrderType.QUARTERLY), unit="季度",
            original_price=None, discount_tag=None, sort_order=5,
            features=[
                TierFeature(icon="📚", title="全量图书无限阅读", desc="平台所有图书随时在线阅读"),
                TierFeature(icon="🎯", title="A-Z 26级晋级体系", desc="科学分级，循序渐进提升阅读能力"),
                TierFeature(icon="🏆", title="排行榜竞技", desc="与同龄小伙伴比拼阅读量"),
                TierFeature(icon="📜", title="晋级证书", desc="每通过一级获得专属晋级证书"),
                TierFeature(icon="⭐", title="成就系统", desc="丰富的成就徽章记录每个里程碑"),
            ],
            cta="立即开通",
        ),
    ]
    return ProductTiersResponse(tiers=tiers)


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
    """支付回调 — 通过支付网关验签 + 解密"""
    import json

    from backend.common.dependencies import get_payment_gateway

    body = await request.body()
    headers = dict(request.headers)
    gateway = get_payment_gateway()

    signature = headers.get("wechatpay-signature", "")
    timestamp = headers.get("wechatpay-timestamp", "")
    nonce = headers.get("wechatpay-nonce", "")
    if not await gateway.verify_callback_signature(body.decode(), signature, timestamp, nonce):
        raise PaymentError("回调验签失败")

    parsed = json.loads(body)
    if "resource" in parsed:
        encrypted = parsed["resource"]
        decrypted = await gateway.decrypt_callback_data(
            encrypted.get("ciphertext", ""),
            encrypted.get("nonce", ""),
            encrypted.get("associated_data", ""),
        )
        callback = OrderPayCallback(
            order_no=decrypted.out_trade_no,
            trade_no=decrypted.transaction_id,
            pay_type=1,
            amount=Decimal(str(decrypted.amount)) / Decimal("100")
            if decrypted.amount is not None else Decimal("0"),
        )
    else:
        callback = OrderPayCallback(**parsed)

    if not callback.order_no:
        raise ValidationError("回调缺少订单号")
    return order_service.handle_payment_callback(callback)


@router.get("/{order_id}/pay-params")
async def get_pay_params(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    order_service: OrderService = Depends(get_order_service),
    current_user=Depends(get_current_user),
    _ctx: tuple = Depends(GetOwnedOrder()),
):
    """获取微信支付参数（前端调用 wx.requestPayment 使用）

    生产环境返回微信支付V3的prepay_id等参数。
    开发/测试环境返回模拟参数。
    """
    _, order = _ctx
    if order.pay_status != 0:
        raise ConflictError("订单状态不允许支付")

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

    # 生产环境：通过支付网关获取真实 prepay_id
    from backend.common.dependencies import get_payment_gateway
    from decimal import ROUND_HALF_UP

    user_repo = UserRepository(db)
    user_orm = user_repo.get_by_id(current_user.id)
    if not user_orm or not user_orm.openid:
        raise PaymentError("用户微信身份异常，无法发起支付")
    openid = user_orm.openid

    gateway = get_payment_gateway()
    amount_cent = int(
        (order.amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    _TYPE_LABELS = {1: "亲子课", 2: "观察期", 3: "正式会员"}
    description = _TYPE_LABELS.get(order.type, "DmkWords 订单")

    pay_params = await gateway.create_jsapi_order(
        openid=openid,
        order_no=order.order_no,
        amount_cent=amount_cent,
        description=description,
    )
    return pay_params


@router.get("/{order_id}/refund-preview", response_model=RefundPreviewResponse)
def preview_refund(
    order_id: int,
    used_days: int = Query(..., ge=0, description="已使用天数"),
    order_service: OrderService = Depends(get_order_service),
    _ctx: tuple = Depends(GetOwnedOrder()),
):
    """预览退款金额"""
    _, order = _ctx
    result: dict[str, Any] = order_service.calculate_refund(order_id, used_days)
    return RefundPreviewResponse(
        order_id=order_id,
        used_days=used_days,
        refund_amount=Decimal(str(result["refund_amount"])),
        daily_rate=Decimal(str(result["daily_rate"])),
        used_amount=Decimal(str(result["used_amount"])),
        total_days=result["total_days"],
    )


@router.get("/upgrade-options/{child_id}", response_model=list[dict])
def get_upgrade_options(
    child_id: int,
    order_service: OrderService = Depends(get_order_service),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询可升级选项及差价"""
    from backend.middleware.ownership import verify_child_ownership
    verify_child_ownership(child_id, current_user, db)
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


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    order_service: OrderService = Depends(get_order_service),
    current_user=Depends(get_current_user),
):
    """取消订单 — 仅可取消未支付的订单"""
    return order_service.cancel_order(order_id, current_user.id)
