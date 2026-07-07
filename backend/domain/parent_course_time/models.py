# backend/domain/parent_course_time/models.py
"""亲子课时间域模型"""

from sqlalchemy import BigInteger, Column, Integer, SmallInteger, String

from backend.common.base_model import BaseModel


class ParentCourseTime(BaseModel):
    """亲子课时间段"""

    __tablename__ = "parent_course_time"
    __table_args__ = {"extend_existing": True}

    venue_id = Column(BigInteger, nullable=False, index=True, comment="场馆ID")
    course_date = Column(String(10), nullable=False, comment="日期 YYYY-MM-DD")
    start_time = Column(String(5), nullable=False, comment="开始时间 HH:MM")
    end_time = Column(String(5), nullable=False, comment="结束时间 HH:MM")
    max_participants = Column(Integer, default=10, comment="最大名额")
    current_participants = Column(Integer, default=0, comment="已报名人数")
    status = Column(SmallInteger, default=1, comment="1=可预约 0=已满 -1=已关闭")
