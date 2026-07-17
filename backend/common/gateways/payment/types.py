# backend/common/gateways/payment/types.py
"""支付网关数据结构 — 业务层与网关层的数据契约"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class PaymentOrderRequest:
    out_trade_no: str
    amount: Decimal
    description: str
    openid: str = ""
    attach: str = ""


@dataclass
class PaymentOrderResponse:
    success: bool
    prepay_id: str = ""
    pay_params: dict = field(default_factory=dict)
    error_message: str = ""


@dataclass
class PaymentRefundRequest:
    out_trade_no: str
    refund_amount: Decimal
    total_amount: Decimal
    reason: str = ""
    out_refund_no: str = ""


@dataclass
class PaymentRefundResponse:
    success: bool
    refund_id: str = ""
    error_message: str = ""


@dataclass
class PaymentCallbackData:
    out_trade_no: str
    transaction_id: str = ""
    trade_state: str = ""
    amount: Optional[Decimal] = None
    raw_body: str = ""
