# backend/domain/message/service.py
"""消息域业务逻辑"""

import logging
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.message.models import SystemMessage
from backend.domain.message.schemas import MessageResponse, MessageListResponse

logger = logging.getLogger(__name__)


class MessageService:
    """消息服务"""

    def __init__(self, db: Session):
        self.db = db
        self.msg_repo = BaseRepository(db, SystemMessage)

    def get_user_messages(
        self,
        user_id: int,
        msg_type: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MessageListResponse:
        """获取用户消息列表"""
        q = self.db.query(SystemMessage).filter(
            SystemMessage.user_id == user_id,
            SystemMessage.is_deleted == 0,
        )
        if msg_type is not None:
            q = q.filter(SystemMessage.msg_type == msg_type)

        total = q.count()
        unread_count = (
            self.db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == user_id,
                SystemMessage.is_read == 0,
                SystemMessage.is_deleted == 0,
            )
            .count()
        )

        messages = (
            q.order_by(SystemMessage.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return MessageListResponse(
            items=[MessageResponse.model_validate(m) for m in messages],
            total=total,
            unread_count=unread_count,
        )

    def mark_as_read(self, message_id: int, user_id: int) -> bool:
        """标记消息已读"""
        msg = (
            self.db.query(SystemMessage)
            .filter(
                SystemMessage.id == message_id,
                SystemMessage.user_id == user_id,
                SystemMessage.is_deleted == 0,
            )
            .first()
        )
        if not msg:
            return False
        msg.is_read = 1
        self.db.commit()
        return True

    def mark_all_read(self, user_id: int) -> int:
        """标记所有消息已读"""
        count = (
            self.db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == user_id,
                SystemMessage.is_read == 0,
                SystemMessage.is_deleted == 0,
            )
            .update({"is_read": 1})
        )
        self.db.commit()
        return count
