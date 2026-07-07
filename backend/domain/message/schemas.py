# backend/domain/message/schemas.py
"""消息域 Pydantic 模型"""

from datetime import datetime

from backend.common.base_schema import BaseSchema


class MessageResponse(BaseSchema):
    """消息响应"""

    id: int
    user_id: int
    title: str
    content: str
    msg_type: int
    priority: int = 0
    is_read: int = 0
    create_time: datetime


class MessageListResponse(BaseSchema):
    """消息列表响应"""

    items: list[MessageResponse]
    total: int
    unread_count: int
