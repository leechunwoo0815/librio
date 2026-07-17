# backend/domain/deposit/schemas.py
"""押金域 Pydantic 模型"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.base_schema import BaseSchema


class DepositPayRequest(BaseSchema):
    child_id: int = Field(..., description="孩子ID")


class DepositRefundRequest(BaseSchema):
    child_id: int = Field(..., description="孩子ID")
    reason: str | None = Field(None, max_length=255, description="退款原因")


class DepositDeductRequest(BaseSchema):
    child_id: int = Field(..., description="孩子ID")
    amount: Decimal = Field(..., gt=0, description="扣除金额")
    reason: str = Field(..., max_length=255, description="扣除原因")


class DepositResponse(BaseSchema):
    id: int
    child_id: int
    amount: Decimal
    status: int
    pay_time: datetime | None = None
    pay_order_id: str | None = None
    refund_time: datetime | None = None
    refund_amount: Decimal | None = None
    deduct_amount: Decimal | None = None
    deduct_reason: str | None = None
    create_time: datetime


class DepositPayResponse(BaseSchema):
    deposit: DepositResponse
    pay_params: dict
