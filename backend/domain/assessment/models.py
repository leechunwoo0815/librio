# backend/domain/assessment/models.py
"""评估域数据模型"""

from sqlalchemy import Column, String, Float, DateTime, Text, ForeignKey, BigInteger
from backend.common.base_model import BaseModel


class Assessment(BaseModel):
    """AR 测评记录"""
    __tablename__ = "assessment"

    child_id = Column(BigInteger, ForeignKey("child.id"), nullable=False, comment="孩子ID")
    teacher_id = Column(BigInteger, ForeignKey("teacher.id"), nullable=True, comment="评估老师ID")
    venue_id = Column(BigInteger, ForeignKey("venue.id"), nullable=True, comment="场馆ID")

    # AR 测评数据
    ar_level_before = Column(Float, nullable=True, comment="测评前 AR 等级")
    ar_level_after = Column(Float, nullable=True, comment="测评后 AR 等级")
    comprehension_score = Column(Float, nullable=True, comment="理解正确率 (%)")

    # 评估状态
    status = Column(String(20), default="pending", nullable=False, comment="状态: pending/completed/scheduled")
    scheduled_date = Column(DateTime, nullable=True, comment="安排的评估日期")
    completed_date = Column(DateTime, nullable=True, comment="完成日期")

    # 备注
    notes = Column(Text, nullable=True, comment="评估备注")
    recommendation = Column(Text, nullable=True, comment="建议")
