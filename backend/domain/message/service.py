# backend/domain/message/service.py
"""消息域业务逻辑"""

import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.message.models import SystemMessage, MessageReadStatus
from backend.domain.message.schemas import MessageResponse, MessageListResponse
from backend.domain.child.models import Child

logger = logging.getLogger(__name__)

_USER_GROUP_MAP = {0: "trial", 1: "observation", 2: "member"}


def _get_user_groups(user_id: int, db: Session) -> set[str]:
    """根据孩子的会员状态推断用户所属分组"""
    children = (
        db.query(Child.status)
        .filter(Child.user_id == user_id, Child.is_deleted == 0)
        .all()
    )
    groups = {_USER_GROUP_MAP.get(c.status, "trial") for c in children}
    return groups or {"trial"}


def _batch_get_read_status(
    message_ids: list[int], user_id: int, db: Session
) -> set[int]:
    """批量查询共享消息的已读状态，返回已读的消息ID集合"""
    if not message_ids:
        return set()
    rows = (
        db.query(MessageReadStatus.message_id)
        .filter(
            MessageReadStatus.message_id.in_(message_ids),
            MessageReadStatus.user_id == user_id,
        )
        .all()
    )
    return {r[0] for r in rows}


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
        """获取用户消息列表 — 包含个人消息和角色群发消息"""
        my_groups = _get_user_groups(user_id, self.db)

        conditions = [
            SystemMessage.user_id == user_id,
            SystemMessage.target_role_codes.is_(None),
        ]
        for g in my_groups:
            conditions.append(SystemMessage.target_role_codes.contains(g))

        q = self.db.query(SystemMessage).filter(
            SystemMessage.is_deleted == 0,
            or_(*conditions),
        )
        if msg_type is not None:
            q = q.filter(SystemMessage.msg_type == msg_type)

        total = q.count()

        messages = (
            q.order_by(SystemMessage.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量查询共享消息的已读状态
        shared_ids = [m.id for m in messages if m.user_id is None]
        read_shared = _batch_get_read_status(shared_ids, user_id, self.db)

        # 计算未读数：个人消息中 is_read=0 + 共享消息中未标记已读
        unread_shared = len(shared_ids) - len(read_shared)
        unread_personal = (
            self.db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == user_id,
                SystemMessage.is_read == 0,
                SystemMessage.is_deleted == 0,
            )
            .count()
        )

        items = []
        for m in messages:
            resp = MessageResponse.model_validate(m)
            if m.user_id is None:
                resp.is_read = 1 if m.id in read_shared else 0
            items.append(resp)

        return MessageListResponse(
            items=items,
            total=total,
            unread_count=unread_personal + unread_shared,
        )

    def mark_as_read(self, message_id: int, user_id: int) -> bool:
        """标记消息已读 — 个人消息直接更新，共享消息写入 MessageReadStatus"""
        msg = (
            self.db.query(SystemMessage)
            .filter(
                SystemMessage.id == message_id,
                SystemMessage.is_deleted == 0,
            )
            .first()
        )
        if not msg:
            return False

        if msg.user_id is not None:
            if msg.user_id != user_id:
                return False
            msg.is_read = 1
        else:
            existing = (
                self.db.query(MessageReadStatus)
                .filter(
                    MessageReadStatus.message_id == message_id,
                    MessageReadStatus.user_id == user_id,
                )
                .first()
            )
            if not existing:
                self.db.add(MessageReadStatus(message_id=message_id, user_id=user_id))

        self.db.commit()
        return True

    def mark_all_read(self, user_id: int) -> int:
        """标记所有消息已读"""
        personal_count = (
            self.db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == user_id,
                SystemMessage.is_read == 0,
                SystemMessage.is_deleted == 0,
            )
            .update({"is_read": 1})
        )

        shared_ids = [
            r[0]
            for r in self.db.query(SystemMessage.id)
            .filter(
                SystemMessage.user_id.is_(None),
                SystemMessage.is_deleted == 0,
            )
            .all()
        ]
        shared_count = 0
        for mid in shared_ids:
            existing = (
                self.db.query(MessageReadStatus)
                .filter(
                    MessageReadStatus.message_id == mid,
                    MessageReadStatus.user_id == user_id,
                )
                .first()
            )
            if not existing:
                self.db.add(MessageReadStatus(message_id=mid, user_id=user_id))
                shared_count += 1

        self.db.commit()
        return personal_count + shared_count
