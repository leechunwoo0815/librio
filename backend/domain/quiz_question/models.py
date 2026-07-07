# backend/domain/quiz_question/models.py
"""测验题目域模型 — 每次测验绑定具体题目"""

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, SmallInteger, String

from backend.common.base_model import BaseModel


class QuizQuestion(BaseModel):
    """测验-题目关联"""

    __tablename__ = "quiz_question"
    __table_args__ = {"extend_existing": True}

    quiz_id = Column(
        BigInteger, ForeignKey("quiz.id"), nullable=False, index=True, comment="测验ID"
    )
    question_id = Column(
        BigInteger, ForeignKey("question_bank.id"), nullable=False, comment="题目ID"
    )
    question_order = Column(Integer, default=0, comment="题目顺序")
    child_answer = Column(String(1), nullable=True, comment="孩子作答 A/B/C/D")
    is_correct = Column(SmallInteger, nullable=True, comment="是否正确 1=对 0=错")
