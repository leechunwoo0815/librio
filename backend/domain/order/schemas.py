# backend/domain/order/schemas.py
"""订单域 Pydantic 模型"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.base_schema import BaseSchema, PaginatedResponse


class OrderCreate(BaseSchema):
    """创建订单请求"""

    child_id: int = Field(..., description="孩子ID")
    type: int = Field(
        ..., ge=1, le=5, description="订单类型: 1=亲子课 2=观察期 3=年费 4=季度 5=半年"
    )
    remark: str | None = Field(None, max_length=255, description="备注")


class OrderResponse(BaseSchema):
    """订单响应"""

    id: int
    order_no: str
    user_id: int
    child_id: int
    type: int
    amount: Decimal
    pay_status: int
    pay_time: datetime | None = None
    pay_type: int | None = None
    trade_no: str | None = None
    refund_status: int = 0
    refund_amount: Decimal | None = None
    remark: str | None = None
    create_time: datetime


class OrderPayCallback(BaseSchema):
    """支付回调请求"""

    order_no: str = Field(..., description="订单编号")
    trade_no: str = Field(..., description="交易流水号")
    pay_type: int = Field(default=1, description="支付方式: 1=微信支付")
    amount: Decimal = Field(..., gt=0, description="实际支付金额")


class RefundPreviewResponse(BaseSchema):
    """退款预览响应"""

    order_id: int
    used_days: int
    refund_amount: Decimal
    daily_rate: Decimal = Decimal("0")
    used_amount: Decimal = Decimal("0")
    total_days: int = 0


OrderListResponse = PaginatedResponse[OrderResponse]


class TierFeature(BaseSchema):
    icon: str = ""
    title: str
    desc: str = ""


class TierInfo(BaseSchema):
    type: int
    name: str
    price: int
    unit: str
    original_price: int | None = None
    discount_tag: str | None = None
    sort_order: int = 0
    features: list[TierFeature] = []
    cta: str = ""


class ProductTiersResponse(BaseSchema):
    tiers: list[TierInfo]
