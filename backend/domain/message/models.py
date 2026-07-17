# backend/domain/message/models.py
"""消息域模型 — 系统消息通知"""

from sqlalchemy import BigInteger, Column, ForeignKey, SmallInteger, String, Text, JSON

from backend.common.base_model import BaseModel


class MessageReadStatus(BaseModel):
    """消息已读状态 — per-user 读追踪（共享消息专用）"""

    __tablename__ = "message_read_status"
    __table_args__ = {"extend_existing": True}

    message_id = Column(
        BigInteger, ForeignKey("system_message.id", ondelete="CASCADE"), nullable=False, index=True, comment="消息ID"
    )
    user_id = Column(
        BigInteger, ForeignKey("user.id"), nullable=False, index=True, comment="用户ID"
    )


class SystemMessage(BaseModel):
    """系统消息"""

    __tablename__ = "system_message"
    __table_args__ = {"extend_existing": True}

    user_id = Column(
        BigInteger, ForeignKey("user.id"), nullable=True, index=True, comment="用户ID(null=角色群发)"
    )
    title = Column(String(100), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    msg_type = Column(
        SmallInteger,
        default=1,
        comment="1=系统通知 2=活动通知 3=借阅通知 4=老师消息 5=阅读提醒",
    )
    priority = Column(SmallInteger, default=0, comment="0=低 1=中 2=高")
    is_read = Column(SmallInteger, default=0, comment="0=未读 1=已读")
    target_role_codes = Column(JSON, nullable=True, comment="可见角色code列表, null=全部可见")


class TeacherMessage(BaseModel):
    """老师消息 — 后台运营向老师发送的通知"""

    __tablename__ = "teacher_message"
    __table_args__ = {"extend_existing": True}

    teacher_id = Column(
        BigInteger, ForeignKey("teacher.id"), nullable=False, index=True, comment="老师ID"
    )
    title = Column(String(100), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    msg_type = Column(
        SmallInteger,
        default=1,
        comment="1=系统通知 2=活动通知 3=借阅通知 4=老师消息 5=阅读提醒",
    )
    priority = Column(SmallInteger, default=0, comment="0=低 1=中 2=高")
    is_read = Column(SmallInteger, default=0, comment="0=未读 1=已读")
