# backend/domain/vocabulary/models.py
"""词汇域模型 — 词典词库 + 用户生词本"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel


class DictionaryWord(BaseModel):
    """系统词库 — ECDICT 338万词条

    注意：DictionaryWord 不需要 update_time / is_deleted，
    但为了简化继承，仍使用 BaseModel。查询时不过滤 is_deleted。
    """

    __tablename__ = "dictionary_word"
    __table_args__ = {"extend_existing": True}

    word = Column(
        String(100), nullable=False, unique=True, index=True, comment="英文单词"
    )
    phonetic = Column(String(100), nullable=True, comment="音标")
    audio_url = Column(String(255), nullable=True, comment="发音URL")
    part_of_speech = Column(String(20), nullable=True, comment="词性")
    chinese_meaning = Column(String(255), nullable=False, comment="中文释义")
    example_sentence = Column(Text, nullable=True, comment="例句")
    level = Column(String(10), nullable=True, comment="难度(A1-C2)")

    user_vocabularies = relationship("UserVocabulary", back_populates="word")


class UserVocabulary(BaseModel):
    """用户生词本"""

    __tablename__ = "user_vocabulary"
    __table_args__ = (
        UniqueConstraint("child_id", "word_id", name="uq_child_word"),
        {"extend_existing": True},
    )

    STATUS_LEARNING = 0
    STATUS_MASTERED = 1

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    word_id = Column(
        BigInteger,
        ForeignKey("dictionary_word.id"),
        nullable=False,
        comment="词典词条ID",
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=True, comment="来源图书"
    )
    status = Column(SmallInteger, default=STATUS_LEARNING, comment="0=学习中 1=已掌握")
    lookup_count = Column(Integer, default=1, comment="查询次数")
    last_review_time = Column(DateTime, nullable=True, comment="最后复习时间")

    word = relationship("DictionaryWord", back_populates="user_vocabularies")
