# backend/domain/reservation/models.py
"""预约域模型 — V3.1 新增

预约流程：用户预约 → 锁定库存 → 72小时内取书 → 转为正式借阅
过期：72小时未取书 → 自动释放库存
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, SmallInteger
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

    # 关系
    child = relationship("Child", foreign_keys=[child_id])
    book = relationship("Book", foreign_keys=[book_id])

    def __repr__(self):
        return f"<Reservation(id={self.id}, child={self.child_id}, book={self.book_id}, status={self.status})>"
