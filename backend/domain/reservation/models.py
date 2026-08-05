# backend/domain/reservation/models.py
"""预约域模型 — V3.1 新增

预约流程：用户预约 → 锁定库存 → 72小时内取书 → 转为正式借阅
过期：72小时未取书 → 自动释放库存
"""

from sqlalchemy import (
    BigInteger,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
)
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel
from backend.common.types import ReservationStatus


class Reservation(BaseModel):
    """预约借书 — 锁定库存"""

    __tablename__ = "reservation"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, index=True, comment="图书ID"
    )
    venue_id = Column(BigInteger, nullable=True, comment="预约取书场馆")

    status = Column(SmallInteger, default=ReservationStatus.PENDING, comment="预约状态")
    expire_time = Column(
        DateTime, nullable=False, index=True, comment="过期时间（创建+72小时）"
    )
    fulfilled_time = Column(DateTime, nullable=True, comment="取书时间")
    borrow_record_id = Column(
        BigInteger, nullable=True, comment="取书后关联的借阅记录ID"
    )
    pickup_reminded = Column(
        SmallInteger,
        default=0,
        comment="取书提醒已发: 0=否 1=是（B4：到期前24h提醒）",
    )

    # 关系
    child = relationship("Child", foreign_keys=[child_id])
    book = relationship("Book", foreign_keys=[book_id])

    def __repr__(self):
        return f"<Reservation(id={self.id}, child={self.child_id}, book={self.book_id}, status={self.status})>"


class BookWaitlist(BaseModel):
    """图书等候名单 — F4：库存为 0 时家长可加入等候，到货/释放自动通知（先到先得）"""

    __tablename__ = "book_waitlist"
    __table_args__ = (
        Index(
            "uq_book_waitlist_active",
            "active_child_book",
            unique=True,
        ),
        {"extend_existing": True},
    )

    STATUS_WAITING = 0
    STATUS_NOTIFIED = 1
    STATUS_FULFILLED = 2
    STATUS_CANCELLED = 3

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, index=True, comment="图书ID"
    )
    status = Column(SmallInteger, default=STATUS_WAITING, comment="等候状态")
    notify_time = Column(DateTime, nullable=True, comment="到货通知时间")
    active_child_book = Column(
        BigInteger,
        Computed(
            "CASE WHEN status IN (0,1) THEN child_id * 1000000 + book_id ELSE NULL END",
            persisted=True,
        ),
        nullable=True,
        comment="F71-⑥：活跃等候唯一键（WAITING/NOTIFIED 时 child×book，防并发重复入队）",
    )

    # 关系
    child = relationship("Child", foreign_keys=[child_id])
    book = relationship("Book", foreign_keys=[book_id])

    def __repr__(self):
        return f"<BookWaitlist(id={self.id}, child={self.child_id}, book={self.book_id}, status={self.status})>"
