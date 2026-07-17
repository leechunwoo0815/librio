# backend/domain/message/schemas.py
"""消息域 Pydantic 模型"""

from datetime import datetime

from backend.common.base_schema import BaseSchema, PaginatedResponse


class MessageResponse(BaseSchema):
    """消息响应"""

    id: int
    user_id: int | None = None
    title: str
    content: str
    msg_type: int
    priority: int = 0
    is_read: int = 0
    create_time: datetime
    target_role_codes: list[str] | None = None


class MessageListResponse(PaginatedResponse[MessageResponse]):
    """消息列表响应"""

    unread_count: int = 0
