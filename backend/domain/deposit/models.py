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
    pay_order_id = Column(
        String(64),
        nullable=True,
        comment="支付单号（DP前缀字符串，审查 P0-1 修正列类型）",
    )

    refund_time = Column(DateTime, nullable=True, comment="退款时间")
    refund_amount = Column(Numeric(10, 2), nullable=True, comment="退款金额")
    original_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="原支付单金额快照（F54：600 奖励退款后 amount 被扣减，退款 total 一律用原额）",
    )
    deduct_amount = Column(Numeric(10, 2), nullable=True, comment="扣除金额")
    deduct_reason = Column(String(255), nullable=True, comment="扣除原因")
    partial_refunded = Column(
        SmallInteger,
        default=0,
        comment="已减半退还: 0=否 1=是（A2：借满N本无逾期可退一半）",
    )
    out_refund_no = Column(
        String(64),
        nullable=True,
        comment="微信商户退款单号（F38：审核通过时生成持久化，重试复用防重复退款）",
    )
    partial_refund_no = Column(
        String(64),
        nullable=True,
        comment="600 奖励退款单号（F76：与全额退款 out_refund_no 分列，避免微信幂等键冲突）",
    )

    # 关系
    child = relationship("Child", foreign_keys=[child_id])

    def __repr__(self):
        return f"<DepositRecord(id={self.id}, child={self.child_id}, status={self.status}, amount={self.amount})>"


class FinePayment(BaseModel):
    """罚款缴纳记录 — B12：家长线上缴纳 outstanding_fines"""

    __tablename__ = "fine_payment"
    __table_args__ = {"extend_existing": True}

    STATUS_PENDING = 0
    STATUS_PAID = 1

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    amount = Column(Numeric(10, 2), nullable=False, comment="缴纳金额（元）")
    status = Column(SmallInteger, default=STATUS_PENDING, comment="支付状态")
    pay_order_no = Column(
        String(32), nullable=True, unique=True, index=True, comment="支付单号"
    )
    pay_time = Column(DateTime, nullable=True, comment="支付时间")

    child = relationship("Child", foreign_keys=[child_id])

    def __repr__(self):
        return f"<FinePayment(id={self.id}, child={self.child_id}, amount={self.amount}, status={self.status})>"
