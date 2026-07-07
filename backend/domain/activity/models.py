# backend/domain/activity/models.py
"""活动域模型 — 活动管理/报名"""

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


class Activity(BaseModel):
    """活动模型"""

    __tablename__ = "activity"
    __table_args__ = {"extend_existing": True}

    TYPE_READING = 1
    TYPE_LECTURE = 2
    TYPE_CITY_WALK = 3
    TYPE_OUTING = 4
    TYPE_MEGAWORDS = 5
    TYPE_OTHER = 6

    STATUS_DRAFT = 0
    STATUS_ENROLLING = 1
    STATUS_ENROLL_CLOSED = 2
    STATUS_IN_PROGRESS = 3
    STATUS_FINISHED = 4
    STATUS_CANCELLED = 5

    title = Column(String(100), nullable=False, comment="活动标题")
    type = Column(
        SmallInteger,
        nullable=False,
        comment="1=读书交流 2=讲座 3=CityWalk 4=郊游 5=大会 6=其他",
    )
    is_free = Column(SmallInteger, default=1, comment="1=免费 0=收费")
    cover = Column(String(255), nullable=True, comment="封面URL")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=False, comment="结束时间")
    enroll_deadline = Column(DateTime, nullable=True, comment="报名截止时间")
    venue_id = Column(BigInteger, nullable=True, comment="场馆ID")
    max_participants = Column(Integer, default=30, comment="最大参与人数")
    current_participants = Column(Integer, default=0, comment="当前参与人数")
    price = Column(Numeric(10, 2), nullable=True, comment="价格")
    description = Column(Text, nullable=True, comment="活动描述")
    location = Column(String(100), nullable=True, comment="活动地点")
    status = Column(SmallInteger, default=STATUS_DRAFT, comment="活动状态")

    enrollments = relationship(
        "ActivityEnrollment",
        back_populates="activity",
        foreign_keys="ActivityEnrollment.activity_id",
    )


class ActivityEnrollment(BaseModel):
    """活动报名"""

    __tablename__ = "activity_enrollment"
    __table_args__ = {"extend_existing": True}

    STATUS_PENDING = 0
    STATUS_APPROVED = 1
    STATUS_REJECTED = 2
    STATUS_CANCELLED = 3
    STATUS_SIGNED_IN = 4

    activity_id = Column(
        BigInteger,
        ForeignKey("activity.id"),
        nullable=False,
        index=True,
        comment="活动ID",
    )
    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    ticket_code = Column(String(32), nullable=False, unique=True, comment="票码")
    sign_in_time = Column(DateTime, nullable=True, comment="签到时间")
    admin_remark = Column(String(255), nullable=True, comment="管理员备注")
    status = Column(SmallInteger, default=STATUS_PENDING, comment="报名状态")

    activity = relationship(
        "Activity", back_populates="enrollments", foreign_keys=[activity_id]
    )
