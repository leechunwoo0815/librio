# backend/domain/audio/models.py
"""音频域数据模型"""

from sqlalchemy import Column, BigInteger, String, Integer
from backend.common.base_model import BaseModel


class AudioFile(BaseModel):
    """音频文件"""

    __tablename__ = "audio_file"

    filename = Column(String(255), nullable=False, comment="文件名")
    file_url = Column(String(500), nullable=False, comment="文件URL")
    book_id = Column(BigInteger, nullable=True, comment="关联图书ID")
    book_title = Column(String(200), nullable=True, comment="关联图书标题（冗余）")
    page_number = Column(Integer, nullable=True, comment="关联页面号（null=全文）")
    page_label = Column(
        String(50), nullable=True, comment="页面标签（如 '全文'/'P1-10'）"
    )
    duration = Column(String(20), nullable=True, comment="时长（如 '3:45'）")
    duration_seconds = Column(Integer, nullable=True, comment="时长（秒）")
    reader = Column(String(100), nullable=True, comment="朗读者")
    status = Column(
        String(20), default="linked", nullable=False, comment="状态: linked/pending"
    )
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
