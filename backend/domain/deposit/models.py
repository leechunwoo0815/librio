# backend/domain/deposit/models.py
"""押金域模型 — V3.1 新增

状态机：UNPAID → PAID → REFUNDED / DEDUCTED
押金金额默认 1200 元。
退款时需校验：借阅记录全部归还、无未缴罚款。
扣除场景：图书丢失、严重损坏。
"""

from decimal import Decimal as D
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel
from backend.common.types import DepositStatus


class DepositRecord(BaseModel):
    """押金记录 — 状态机管理"""

    __tablename__ = "deposit_record"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    amount = Column(
        Numeric(10, 2), nullable=False, default=D("1200.00"), comment="押金金额"
    )
    status = Column(SmallInteger, default=DepositStatus.UNPAID, comment="押金状态")

    pay_time = Column(DateTime, nullable=True, comment="支付时间")
    pay_order_id = Column(BigInteger, nullable=True, comment="支付订单ID")

    refund_time = Column(DateTime, nullable=True, comment="退款时间")
    refund_amount = Column(Numeric(10, 2), nullable=True, comment="退款金额")
    deduct_amount = Column(Numeric(10, 2), nullable=True, comment="扣除金额")
    deduct_reason = Column(String(255), nullable=True, comment="扣除原因")

    # 关系
    child = relationship("Child", foreign_keys=[child_id])

    def __repr__(self):
        return f"<DepositRecord(id={self.id}, child={self.child_id}, status={self.status}, amount={self.amount})>"
