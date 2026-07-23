# backend/domain/user/consent_model.py
"""用户同意记录模型 — 三段式监护人同意（隐私政策/儿童信息/语音录制）"""

from sqlalchemy import BigInteger, Column, DateTime, Index, String

from backend.common.base_model import BaseModel


class ConsentRecord(BaseModel):
    """用户同意记录 — 合规证据，永不物理删除"""

    __tablename__ = "consent_record"
    __table_args__ = (
        Index("idx_consent_user_type", "user_id", "consent_type"),
        Index("idx_consent_created", "create_time"),
    )

    CONSENT_TYPE_PRIVACY = "privacy_policy"
    CONSENT_TYPE_CHILD_DATA = "child_data"
    CONSENT_TYPE_VOICE = "voice_recording"
    VALID_TYPES = {CONSENT_TYPE_PRIVACY, CONSENT_TYPE_CHILD_DATA, CONSENT_TYPE_VOICE}

    user_id = Column(BigInteger, nullable=False, index=True, comment="用户ID")
    consent_type = Column(
        String(50), nullable=False, comment="同意类型: privacy_policy/child_data/voice_recording"
    )
    consent_text_hash = Column(
        String(64), nullable=False, comment="同意文案SHA-256哈希，追溯当时版本"
    )
    consent_version = Column(String(20), nullable=False, comment="隐私政策版本号")
    ip_address = Column(String(45), nullable=True, comment="IP地址")
    user_agent = Column(String(500), nullable=True, comment="User-Agent")
    withdrawn_at = Column(DateTime, nullable=True, comment="撤回时间，NULL=有效")
