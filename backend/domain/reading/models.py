# backend/domain/reading/models.py
"""阅读行为域模型 — 进度/会话/打卡/分页内容"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)

from backend.common.base_model import BaseModel


class BookPage(BaseModel):
    """图书分页内容"""

    __tablename__ = "book_page"
    __table_args__ = {"extend_existing": True}

    CONTENT_TEXT = 0
    CONTENT_IMAGE = 1
    CONTENT_MIXED = 2

    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, index=True, comment="图书ID"
    )
    page_number = Column(Integer, nullable=False, comment="页码")
    content_type = Column(
        SmallInteger, default=CONTENT_TEXT, comment="0=文本 1=图片 2=图文混合"
    )
    text_content = Column(Text, nullable=True, comment="文本内容")
    image_url = Column(String(255), nullable=True, comment="图片URL")
    audio_url = Column(String(255), nullable=True, comment="该页音频URL")
    audio_duration = Column(Integer, nullable=True, comment="音频时长(秒)")

    def __repr__(self):
        return f"<BookPage(book={self.book_id}, page={self.page_number})>"


class ReadingProgress(BaseModel):
    """阅读进度，每个child+book一条记录"""

    __tablename__ = "reading_progress"
    __table_args__ = (
        UniqueConstraint("child_id", "book_id", name="uq_child_book_progress"),
        {"extend_existing": True},
    )

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, comment="图书ID"
    )
    current_page = Column(Integer, default=1, comment="当前页码")
    total_pages = Column(Integer, nullable=False, comment="总页数")
    progress_pct = Column(Numeric(5, 2), default=0, comment="进度百分比")
    last_read_time = Column(DateTime, nullable=True, comment="最后阅读时间")
    is_finished = Column(SmallInteger, default=0, comment="是否读完: 0=否 1=是")
    finish_time = Column(DateTime, nullable=True, comment="读完时间")

    def __repr__(self):
        return f"<ReadingProgress(child={self.child_id}, book={self.book_id}, page={self.current_page})>"


class ReadingSession(BaseModel):
    """单次阅读会话记录"""

    __tablename__ = "reading_session"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, comment="图书ID"
    )
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    duration_seconds = Column(Integer, default=0, comment="阅读时长(秒)")
    pages_read = Column(Integer, default=0, comment="本次阅读页数")
    words_read = Column(Integer, default=0, comment="本次阅读词数")

    def __repr__(self):
        return f"<ReadingSession(child={self.child_id}, duration={self.duration_seconds}s)>"


class CheckIn(BaseModel):
    """每日阅读打卡"""

    __tablename__ = "check_in"
    __table_args__ = {"extend_existing": True}

    TYPE_READING = 1
    TYPE_FINISH_BOOK = 2
    TYPE_VOICE = 3
    TYPE_VOCABULARY = 4

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, comment="孩子ID"
    )
    check_date = Column(Date, nullable=False, comment="打卡日期")
    check_type = Column(
        SmallInteger, nullable=False, comment="1=阅读 2=读完 3=朗读 4=生词"
    )
    reading_minutes = Column(Integer, default=0, comment="阅读分钟数")
    words_read = Column(Integer, default=0, comment="阅读词数")
    books_finished = Column(Integer, default=0, comment="读完本数")
    new_words = Column(Integer, default=0, comment="新增生词数")

    def __repr__(self):
        return f"<CheckIn(child={self.child_id}, date={self.check_date}, type={self.check_type})>"


class VoiceRecording(BaseModel):
    """语音朗读记录"""

    __tablename__ = "voice_recording"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, comment="图书ID"
    )
    page_id = Column(BigInteger, nullable=True, comment="关联页面")
    text_content = Column(Text, nullable=False, comment="朗读文本")
    audio_url = Column(String(255), nullable=False, comment="录音URL")
    duration_seconds = Column(Integer, nullable=False, comment="录音时长(秒)")
    pronunciation_score = Column(Numeric(3, 1), nullable=True, comment="发音评分")
    fluency_score = Column(Numeric(3, 1), nullable=True, comment="流利度评分")
    completeness_score = Column(Numeric(3, 1), nullable=True, comment="完整度评分")

    def __repr__(self):
        return f"<VoiceRecording(child={self.child_id}, book={self.book_id}, duration={self.duration_seconds}s)>"
