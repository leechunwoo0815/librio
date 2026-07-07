# backend/domain/voice/models.py
"""语音域模型 — 语音朗读记录和评分"""

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, Numeric, String, Text

from backend.common.base_model import BaseModel


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
