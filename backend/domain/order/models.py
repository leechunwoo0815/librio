# backend/domain/order/models.py
"""订单域模型 — 订单/支付"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
)

from backend.common.base_model import BaseModel
from backend.common.types import PayStatus


class Order(BaseModel):
    """订单模型 — 统一管理所有类型订单"""

    TYPE_PARENT_COURSE = 1
    TYPE_OBSERVATION = 2
    TYPE_OFFICIAL_MEMBER = 3
    PAY_PENDING = 0
    PAY_PAID = 1
    PAY_REFUNDING = 3
    PAY_CLOSED = 5
    REFUND_NONE = 0
    REFUND_PROCESSING = 1
    REFUND_DONE = 2
    REFUND_FAILED = 3
    __tablename__ = "order"
    __table_args__ = {"extend_existing": True}

    order_no = Column(
        String(32), nullable=False, unique=True, index=True, comment="订单编号"
    )
    user_id = Column(
        BigInteger, ForeignKey("user.id"), nullable=False, index=True, comment="用户ID"
    )
    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )

    type = Column(
        SmallInteger, nullable=False, comment="订单类型: 1=亲子课 2=观察期 3=正式会员"
    )
    amount = Column(Numeric(10, 2), nullable=False, comment="订单金额(元)")

    pay_status = Column(SmallInteger, default=PayStatus.PENDING, comment="支付状态")
    pay_time = Column(DateTime, nullable=True, comment="支付时间")
    pay_type = Column(
        SmallInteger, nullable=True, comment="支付方式: 1=微信支付 2=对公转账"
    )
    trade_no = Column(String(64), nullable=True, comment="第三方交易流水号")

    refund_status = Column(
        SmallInteger,
        default=0,
        comment="退款状态: 0=未退款 1=退款中 2=已退款 3=退款失败",
    )
    refund_amount = Column(Numeric(10, 2), nullable=True, comment="已退款金额")
    refund_time = Column(DateTime, nullable=True, comment="退款完成时间")

    remark = Column(String(255), nullable=True, comment="订单备注")

    def __repr__(self):
        return f"<Order(id={self.id}, order_no='{self.order_no}', type={self.type}, pay_status={self.pay_status})>"
