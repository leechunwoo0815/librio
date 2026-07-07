# backend/domain/report/models.py
"""报告域模型 — 观察期报告 + 学习报告"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel


class ObservationReport(BaseModel):
    """观察期报告 — 30天自动生成"""

    __tablename__ = "observation_report"
    __table_args__ = {"extend_existing": True}

    STATUS_GENERATED = 1
    STATUS_VIEWED = 2

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    start_date = Column(DateTime, nullable=False, comment="观察期开始日期")
    end_date = Column(DateTime, nullable=False, comment="观察期结束日期")

    total_reading_minutes = Column(Integer, default=0, comment="总阅读分钟")
    total_books_read = Column(Integer, default=0, comment="读完本书数")
    total_words_read = Column(Integer, default=0, comment="总阅读词数")
    avg_daily_minutes = Column(Integer, default=0, comment="日均阅读分钟")

    level_at_start = Column(String(20), nullable=True, comment="起始级别")
    level_at_end = Column(String(20), nullable=True, comment="结束级别")

    quizzes_attempted = Column(Integer, default=0, comment="测验尝试次数")
    quizzes_passed = Column(Integer, default=0, comment="测验通过次数")
    teacher_id = Column(BigInteger, nullable=True, comment="负责老师ID")

    teacher_comment = Column(Text, nullable=True, comment="老师评语")
    recommendation = Column(String(255), nullable=True, comment="推荐方案")
    status = Column(SmallInteger, default=0, comment="0=草稿 1=已生成")

    child = relationship("Child", foreign_keys=[child_id])


class LearningReport(BaseModel):
    """学习报告"""

    __tablename__ = "learning_report"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    period_type = Column(String(10), nullable=False, comment="报告周期: weekly/monthly")
    period_start = Column(DateTime, nullable=False, comment="周期开始")
    period_end = Column(DateTime, nullable=False, comment="周期结束")

    reading_minutes = Column(Integer, default=0, comment="阅读分钟")
    books_finished = Column(Integer, default=0, comment="读完本数")
    words_read = Column(Integer, default=0, comment="阅读词数")
    new_vocabulary = Column(Integer, default=0, comment="新增生词数")
    mastered_vocabulary = Column(Integer, default=0, comment="掌握生词数")

    summary = Column(Text, nullable=True, comment="AI 生成摘要")

    child = relationship("Child", foreign_keys=[child_id])
