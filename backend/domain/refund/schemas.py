# backend/domain/refund/schemas.py
"""退款域 Pydantic 模型"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.base_schema import BaseSchema


class RefundCreate(BaseSchema):
    order_id: int = Field(..., description="订单ID")
    used_days: int = Field(..., ge=0, description="已使用天数")
    reason: str = Field(..., max_length=255, description="退款原因")
    damage_amount: Decimal | None = Field(None, ge=0, description="图书损坏赔偿金额")


class RefundAudit(BaseSchema):
    status: int = Field(..., ge=1, le=2, description="1=审核通过 2=审核拒绝")
    admin_id: int | None = Field(None, description="管理员ID（由后端从认证上下文获取）")
    remark: str | None = Field(None, max_length=255, description="审核备注")


class RefundResponse(BaseSchema):
    id: int
    order_id: int
    user_id: int
    child_id: int
    refund_amount: Decimal
    used_days: int = 0
    reason: str | None = None
    status: int
    reviewer_id: int | None = None
    review_time: datetime | None = None
    review_comment: str | None = None
    actual_refund_amount: Decimal | None = None
    create_time: datetime
