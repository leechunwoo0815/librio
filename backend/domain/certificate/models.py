# backend/domain/certificate/models.py
"""证书域模型 — 晋级证书"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel


class LevelCertificate(BaseModel):
    """晋级证书"""

    __tablename__ = "level_certificate"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    level_id = Column(
        BigInteger, ForeignKey("level.id"), nullable=False, comment="级别ID"
    )
    level_name = Column(String(50), nullable=False, comment="级别名称（冗余）")

    child_name = Column(String(50), nullable=True, comment="孩子姓名")
    child_english_name = Column(String(50), nullable=True, comment="孩子英文名")
    badge_emoji = Column(String(10), nullable=True, comment="徽章Emoji")
    certificate_no = Column(String(50), nullable=False, unique=True, comment="证书编号")
    issued_at = Column(DateTime, nullable=True, comment="颁发时间")
    template_html = Column(String(500), nullable=True, comment="证书HTML模板路径")

    child = relationship("Child", foreign_keys=[child_id])
