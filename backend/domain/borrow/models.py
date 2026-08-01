# backend/domain/borrow/models.py
"""借阅域模型 — V3.1 OMO 核心表

线下借阅记录，与 Bookshelf（想读清单）完全分离。
借阅上限由配置 borrow_limit 控制（默认 10 本，B14 决策）。
借期 21 天，到期前 5/3/1/当天发订阅消息提醒。
逾期宽限期 overdue_grace_days（默认 3 天）内免罚、音频不锁（B7/B8 决策）。
积分去重：排行榜统计时，同一 child_id + book_id 的 word_count 只计一次。
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel
from backend.common.types import BorrowStatus


class BorrowRecord(BaseModel):
    """线下借阅记录 — OMO 模式核心表"""

    __tablename__ = "borrow_record"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, index=True, comment="图书ID"
    )
    book_copy_id = Column(
        BigInteger, ForeignKey("book_copy.id"), nullable=True, comment="具体副本ID"
    )
    operator_id = Column(BigInteger, nullable=True, comment="操作运营人员ID")

    borrow_time = Column(DateTime, nullable=False, comment="借出时间")
    due_date = Column(
        DateTime, nullable=False, index=True, comment="应还日期（借出+21天）"
    )
    return_time = Column(DateTime, nullable=True, comment="实际归还时间")
    status = Column(
        SmallInteger, default=BorrowStatus.BORROWING, index=True, comment="借阅状态"
    )

    # 逾期相关
    overdue_days = Column(Integer, default=0, comment="逾期天数")
    fine_amount = Column(Numeric(10, 2), default=0, comment="逾期服务费（实际应收）")
    fine_original = Column(
        Numeric(10, 2), nullable=True, comment="免罚前计算金额（B7审计用）"
    )
    fine_waived = Column(
        SmallInteger, default=0, comment="首次逾期免罚: 0=否 1=是（B7）"
    )

    # 测评去重标记
    quiz_passed = Column(SmallInteger, default=0, comment="是否已通过测评: 0=否 1=是")

    # B9/B10 损坏丢失流程
    checkout_photos = Column(
        String(500),
        nullable=True,
        comment="借出时拍照存档（JSON数组：封面/封底/书脊，B9）",
    )
    lost_search_deadline = Column(
        DateTime, nullable=True, comment="丢失寻找期截止（登记+7天，B10：期内找回免赔）"
    )

    # 关系
    child = relationship("Child", foreign_keys=[child_id])
    book = relationship("Book", foreign_keys=[book_id])
    book_copy = relationship("BookCopy", foreign_keys=[book_copy_id])

    def __repr__(self):
        return f"<BorrowRecord(id={self.id}, child={self.child_id}, book={self.book_id}, status={self.status})>"
