# backend/common/dead_letter_model.py
"""死信事件表 — 记录失败的事件处理器"""

from sqlalchemy import Column, String, Text, SmallInteger
from backend.common.base_model import BaseModel


class DeadLetterEvent(BaseModel):
    """死信事件"""

    __tablename__ = "dead_letter_event"
    __table_args__ = {"extend_existing": True}

    event_type = Column(String(50), nullable=False, index=True, comment="事件类型")
    event_data = Column(Text, nullable=False, comment="事件数据 JSON")
    handler_name = Column(String(100), nullable=False, comment="处理器名称")
    error_message = Column(Text, nullable=True, comment="错误信息")
    retry_count = Column(SmallInteger, default=0, comment="重试次数")
    resolved_at = Column(String(30), nullable=True, comment="解决时间")
