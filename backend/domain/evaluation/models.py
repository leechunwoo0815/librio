# backend/domain/evaluation/models.py
"""测评域模型 — AR测评、观察期评价、指导记录"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
)

from backend.common.base_model import BaseModel


class AREvaluation(BaseModel):
    """AR测评记录"""

    __tablename__ = "ar_evaluation"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    ar_level = Column(Numeric(3, 1), nullable=False, comment="AR级别")
    evaluation_date = Column(DateTime, nullable=False, comment="测评日期")
    teacher_id = Column(BigInteger, nullable=True, comment="老师ID")
    remark = Column(Text, nullable=True, comment="备注")


class ObservationEvaluation(BaseModel):
    """观察期评价"""

    __tablename__ = "observation_evaluation"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    teacher_id = Column(BigInteger, nullable=False, comment="老师ID")
    reading_interest = Column(SmallInteger, nullable=False, comment="阅读兴趣 1-5")
    reading_speed = Column(SmallInteger, nullable=False, comment="阅读速度 1-5")
    comprehension = Column(SmallInteger, nullable=False, comment="理解能力 1-5")
    independent_reading = Column(SmallInteger, nullable=False, comment="自主阅读 1-5")
    total_score = Column(Integer, nullable=False, comment="总分")
    result = Column(SmallInteger, nullable=False, comment="1=通过 2=待定 3=不通过")
    remark = Column(Text, nullable=True, comment="备注")
    evaluation_date = Column(DateTime, nullable=False, comment="评价日期")


class GuidanceRecord(BaseModel):
    """指导记录"""

    __tablename__ = "guidance_record"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    teacher_id = Column(BigInteger, nullable=False, comment="老师ID")
    content = Column(Text, nullable=False, comment="指导内容")
    guidance_date = Column(DateTime, nullable=False, comment="指导日期")
