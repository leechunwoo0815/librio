# backend/domain/refund/models.py
"""退款域模型"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel


class RefundApplication(BaseModel):
    """退款申请"""

    __tablename__ = "refund_application"
    __table_args__ = {"extend_existing": True}

    STATUS_PENDING = 0
    STATUS_APPROVED = 1
    STATUS_REJECTED = 2
    STATUS_COMPLETED = 3

    order_id = Column(
        BigInteger,
        ForeignKey("order.id"),
        nullable=False,
        index=True,
        comment="关联订单ID",
    )
    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    user_id = Column(
        BigInteger, ForeignKey("user.id"), nullable=False, index=True, comment="用户ID"
    )

    amount = Column(Numeric(10, 2), nullable=True, comment="订单原金额")
    refund_amount = Column(Numeric(10, 2), nullable=False, comment="申请退款金额")
    used_days = Column(Integer, nullable=True, comment="已使用天数")
    reason = Column(String(255), nullable=True, comment="退款原因")
    status = Column(SmallInteger, default=STATUS_PENDING, comment="退款状态")

    reviewer_id = Column(BigInteger, nullable=True, comment="审核人ID")
    review_time = Column(DateTime, nullable=True, comment="审核时间")
    review_comment = Column(Text, nullable=True, comment="审核意见")

    actual_refund_amount = Column(Numeric(10, 2), nullable=True, comment="实际退款金额")
    refund_time = Column(DateTime, nullable=True, comment="退款完成时间")

    order = relationship("Order", foreign_keys=[order_id])
