# backend/domain/advancement/models.py
"""晋级域模型 — 级别/测验/成就

V3.1 重构核心：QuizService 解耦
  重构前：submit_answers() 做 7 件事（评分→更新ChildLevel→更新统计→还书→提交→晋级→成就）
  重构后：submit_answers() 只做评分+发布 QuizPassedEvent
  其他域各自订阅事件自行响应
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class Level(BaseModel):
    """级别定义 — 管理员可配置"""

    __tablename__ = "level"
    __table_args__ = {"extend_existing": True}

    name = Column(String(50), nullable=False, unique=True, comment="级别名称")
    code = Column(String(10), nullable=True, index=True, comment="级别代码（如 A-Z）")
    badge_icon = Column(String(255), nullable=True, comment="徽章图标URL")
    badge_emoji = Column(String(10), nullable=True, comment="徽章Emoji")
    sort_order = Column(Integer, default=0, comment="排序序号（越小越初级）")

    # 晋级要求
    required_books = Column(Integer, default=5, comment="需要读完几本书才能晋级")
    required_quiz_pass_rate = Column(
        Numeric(3, 2), default=0.80, comment="测验最低通过率"
    )
    require_teacher_review = Column(Boolean, default=False, comment="是否需要老师审核")

    # 晋级权限
    max_borrow_count = Column(Integer, default=1, comment="最大同时借阅数")
    max_ar_level = Column(Numeric(3, 1), nullable=True, comment="最大可读AR等级")


class ChildLevel(BaseModel):
    """孩子级别记录 — 当前级别+晋级历史"""

    __tablename__ = "child_level"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    level_id = Column(
        BigInteger, ForeignKey("level.id"), nullable=False, comment="级别ID"
    )
    achieved_at = Column(DateTime, nullable=True, comment="达到该级别的时间")
    books_read_at_level = Column(Integer, default=0, comment="在该级别已读完的书数")
    quizzes_passed_at_level = Column(Integer, default=0, comment="在该级别通过的测验数")
    is_current = Column(Boolean, default=True, comment="是否当前级别")

    level = relationship("Level")


class ReadingSubmission(BaseModel):
    """阅读提交 — 孩子读完最后一页自动创建"""

    __tablename__ = "reading_submission"
    __table_args__ = {"extend_existing": True}

    STATUS_PENDING = 0
    STATUS_APPROVED = 1
    STATUS_REJECTED = 2

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, comment="图书ID"
    )
    teacher_id = Column(BigInteger, nullable=True, comment="负责审核的老师ID")
    status = Column(SmallInteger, default=STATUS_PENDING, comment="审核状态")
    teacher_comment = Column(Text, nullable=True, comment="老师评语")
    submitted_at = Column(
        DateTime, default=datetime.utcnow, nullable=True, comment="提交时间"
    )
    word_count = Column(Integer, default=0, comment="该本书的单词数（积分用）")
    reviewed_at = Column(DateTime, nullable=True, comment="审核时间")


class QuestionBank(BaseModel):
    """题库 — 每本书的选择题"""

    __tablename__ = "question_bank"
    __table_args__ = {"extend_existing": True}

    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, index=True, comment="图书ID"
    )
    question_text = Column(Text, nullable=False, comment="题目文本")
    option_a = Column(String(255), nullable=False, comment="选项A")
    option_b = Column(String(255), nullable=False, comment="选项B")
    option_c = Column(String(255), nullable=True, comment="选项C")
    option_d = Column(String(255), nullable=True, comment="选项D")
    correct_answer = Column(String(1), nullable=False, comment="正确答案(A/B/C/D)")
    explanation = Column(Text, nullable=True, comment="答案解析")
    difficulty = Column(SmallInteger, default=1, comment="难度1-5")
    created_by = Column(BigInteger, nullable=True, comment="创建者ID（老师）")


class Quiz(BaseModel):
    """测验实例"""

    __tablename__ = "quiz"
    __table_args__ = {"extend_existing": True}

    STATUS_IN_PROGRESS = 0
    STATUS_COMPLETED = 1
    STATUS_EXPIRED = 2

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, comment="图书ID"
    )
    submission_id = Column(
        BigInteger,
        ForeignKey("reading_submission.id"),
        nullable=True,
        comment="关联提交ID",
    )
    teacher_id = Column(BigInteger, nullable=True, comment="出卷老师ID")
    status = Column(SmallInteger, default=STATUS_IN_PROGRESS, comment="测验状态")
    total_questions = Column(Integer, default=5, comment="题目总数")
    correct_count = Column(Integer, default=0, comment="正确数")
    score = Column(Numeric(5, 2), nullable=True, comment="正确率")


class QuizAnswer(BaseModel):
    """测验答题记录"""

    __tablename__ = "quiz_answer"
    __table_args__ = {"extend_existing": True}

    quiz_id = Column(
        BigInteger, ForeignKey("quiz.id"), nullable=False, index=True, comment="测验ID"
    )
    question_id = Column(
        BigInteger, ForeignKey("question_bank.id"), nullable=False, comment="题目ID"
    )
    selected_answer = Column(String(1), nullable=False, comment="选择的答案(A/B/C/D)")
    is_correct = Column(Boolean, nullable=False, comment="是否正确")


class Achievement(BaseModel):
    """成就定义"""

    __tablename__ = "achievement"
    __table_args__ = {"extend_existing": True}

    TYPE_LEVEL_UP = 1
    TYPE_BOOK_MILESTONE = 2
    TYPE_STREAK = 3
    TYPE_QUIZ_PERFECT = 4

    name = Column(String(50), nullable=False, comment="成就名称")
    description = Column(String(255), nullable=True, comment="成就描述")
    type = Column(SmallInteger, nullable=False, comment="成就类型")
    badge_icon = Column(String(255), nullable=True, comment="徽章图标URL")
    badge_emoji = Column(String(10), nullable=True, comment="徽章Emoji")
    trigger_condition = Column(String(255), nullable=True, comment="触发条件JSON")


class ChildAchievement(BaseModel):
    """孩子已获得的成就"""

    __tablename__ = "child_achievement"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    achievement_id = Column(
        BigInteger, ForeignKey("achievement.id"), nullable=False, comment="成就ID"
    )
    achieved_at = Column(DateTime, nullable=True, comment="获得时间")
    context_data = Column(
        String(255), nullable=True, comment="上下文JSON（如读完第几本书）"
    )

    achievement = relationship("Achievement", foreign_keys=[achievement_id])
