# backend/domain/book/damage_model.py
"""图书损坏报告模型 — T3.6a 三级定责"""

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from backend.common.base_model import BaseModel


class BookDamageReport(BaseModel):
    """图书损坏/丢失报告"""

    __tablename__ = "book_damage_report"
    __table_args__ = {"extend_existing": True}

    LEVEL_LIGHT = 1  # 轻度—免费
    LEVEL_HEAVY = 2  # 重度—0.5×定价
    LEVEL_LOST = 3  # 丢失—1.5×定价

    STATUS_PENDING = 0  # 待申诉（7天申诉期）
    STATUS_CONFIRMED = 1  # 已确认（申诉期过或家长接受）
    STATUS_DISPUTED = 2  # 申诉中
    STATUS_OVERRIDDEN = 3  # 已冲正（管理员改判）

    borrow_record_id = Column(
        BigInteger,
        ForeignKey("borrow_record.id"),
        nullable=False,
        index=True,
        comment="关联借阅记录ID",
    )
    book_copy_id = Column(
        BigInteger,
        ForeignKey("book_copy.id"),
        nullable=True,
        index=True,
        comment="关联副本ID",
    )
    child_id = Column(
        BigInteger,
        ForeignKey("child.id"),
        nullable=False,
        index=True,
        comment="孩子ID",
    )
    damage_level = Column(
        SmallInteger,
        nullable=False,
        comment="定级: 1=轻度免费 2=重度0.5×定价 3=丢失1.5×定价",
    )
    photo_url = Column(String(500), nullable=True, comment="损坏照片URL")
    description = Column(Text, nullable=True, comment="定责说明")
    fine_amount = Column(Numeric(10, 2), nullable=True, comment="罚款金额（元）")
    status = Column(
        SmallInteger,
        default=STATUS_PENDING,
        comment="状态: 0=待申诉 1=已确认 2=申诉中 3=已冲正",
    )
    admin_id = Column(BigInteger, nullable=True, comment="登记管理员ID")
    appeal_reason = Column(Text, nullable=True, comment="申诉理由")
    appeal_result = Column(Text, nullable=True, comment="申诉处理结果")
    override_level = Column(SmallInteger, nullable=True, comment="冲正后定级")
    override_fine = Column(Numeric(10, 2), nullable=True, comment="冲正后罚款金额")
    review_admin_id = Column(BigInteger, nullable=True, comment="申诉/冲正审核管理员ID")
    reviewed_at = Column(String(30), nullable=True, comment="审核时间")
