# backend/domain/child/models.py
"""孩子域模型 — 会员状态、阅读统计"""

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
from backend.common.types import DepositStatus, MemberStatus


class Child(BaseModel):
    """孩子模型"""

    __tablename__ = "child"
    __table_args__ = {"extend_existing": True}

    # 状态常量（向后兼容，旧测试使用 Child.STATUS_XXX）
    STATUS_TRIAL = 0
    STATUS_OBSERVATION = 1
    STATUS_OFFICIAL = 2
    STATUS_EXPIRED = 3
    STATUS_EXITED = 4

    user_id = Column(
        BigInteger,
        ForeignKey("user.id"),
        nullable=False,
        index=True,
        comment="关联用户ID",
    )
    name = Column(String(50), nullable=False, comment="孩子中文姓名")
    english_name = Column(String(50), nullable=True, comment="孩子英文姓名")
    age = Column(SmallInteger, nullable=False, comment="孩子年龄(3-15)")
    grade = Column(String(20), nullable=False, comment="年级")
    status = Column(
        SmallInteger, default=MemberStatus.TRIAL, nullable=False, comment="会员状态"
    )

    member_start_time = Column(DateTime, nullable=True, comment="会员开始时间")
    member_expire_time = Column(DateTime, nullable=True, comment="会员到期时间")
    ar_level = Column(Numeric(3, 1), nullable=True, comment="AR阅读等级")
    teacher_id = Column(BigInteger, nullable=True, comment="指导老师ID")
    venue_id = Column(BigInteger, nullable=True, comment="所属场馆ID")

    # 阅读统计字段
    total_reading_minutes = Column(Integer, default=0, comment="累计阅读分钟")
    total_words_read = Column(Integer, default=0, comment="累计阅读词数")
    total_books_finished = Column(Integer, default=0, comment="累计读完本数")
    current_streak_days = Column(Integer, default=0, comment="连续打卡天数")
    longest_streak_days = Column(Integer, default=0, comment="最长连续打卡")

    # V3.1 新增字段
    deposit_status = Column(
        SmallInteger,
        default=DepositStatus.UNPAID,
        comment="押金状态: 0=未交 1=已交 2=已退 3=已扣",
    )
    outstanding_fines = Column(Numeric(10, 2), default=0, comment="未缴罚款")
    current_level_id = Column(
        BigInteger, nullable=True, comment="当前级别ID（冗余，避免join查询）"
    )

    user = relationship("User", back_populates="children", foreign_keys=[user_id])

    def __repr__(self):
        return f"<Child(id={self.id}, name='{self.name}', status={self.status})>"
