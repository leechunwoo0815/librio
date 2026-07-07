# backend/domain/admin/services/message_service.py
"""管理端消息/通知 Service — 从 AdminService 拆分出来的独立域服务。"""

from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError
from backend.domain.admin.services.system_service import AdminSystemService


class AdminMessageService:
    """运营消息推送、逾期提醒。"""

    def __init__(self, db: Session, system_service: AdminSystemService | None = None):
        self.db = db
        self.system_service = system_service or AdminSystemService(db)

    def send_message(
        self,
        title: str,
        content: str,
        msg_type: int,
        priority: int,
        target: str = "all",
        target_user_id: int | None = None,
    ) -> dict:
        """运营消息推送 — 支持全部/指定用户"""
        from backend.domain.message.models import SystemMessage
        from backend.domain.user.models import User

        if target == "user":
            if not target_user_id:
                raise NotFoundError("指定用户时 target_user_id 不能为空")
            user = (
                self.db.query(User)
                .filter(User.id == target_user_id, User.is_deleted == 0)
                .first()
            )
            if not user:
                raise NotFoundError("目标用户不存在")
            msg = SystemMessage(
                user_id=target_user_id,
                title=title,
                content=content,
                msg_type=msg_type,
                priority=priority,
            )
            self.db.add(msg)
            self.db.commit()
            return {"success": True, "sent_count": 1}

        # 全部用户
        users = self.db.query(User).filter(User.is_deleted == 0).all()
        for u in users:
            msg = SystemMessage(
                user_id=u.id,
                title=title,
                content=content,
                msg_type=msg_type,
                priority=priority,
            )
            self.db.add(msg)
        self.db.commit()
        return {"success": True, "sent_count": len(users)}

    def list_messages(self, page: int = 1, page_size: int = 20) -> dict:
        """已发送消息列表"""
        from backend.domain.message.models import SystemMessage

        total = self.db.query(SystemMessage).filter(SystemMessage.is_deleted == 0).count()
        messages = (
            self.db.query(SystemMessage)
            .filter(SystemMessage.is_deleted == 0)
            .order_by(SystemMessage.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "items": [
                {
                    "id": m.id,
                    "user_id": m.user_id,
                    "title": m.title,
                    "content": m.content,
                    "msg_type": m.msg_type,
                    "priority": m.priority,
                    "is_read": m.is_read,
                    "create_time": m.create_time.isoformat() if m.create_time else None,
                }
                for m in messages
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def mark_message_read(self, message_id: int) -> dict:
        """标记消息已读"""
        from backend.domain.message.models import SystemMessage

        msg = (
            self.db.query(SystemMessage)
            .filter(SystemMessage.id == message_id, SystemMessage.is_deleted == 0)
            .first()
        )
        if not msg:
            raise NotFoundError("消息不存在")
        msg.is_read = True
        self.db.commit()
        return {"success": True}

    def delete_message(self, message_id: int) -> dict:
        """删除消息"""
        from backend.domain.message.models import SystemMessage

        msg = (
            self.db.query(SystemMessage)
            .filter(SystemMessage.id == message_id, SystemMessage.is_deleted == 0)
            .first()
        )
        if not msg:
            raise NotFoundError("消息不存在")
        msg.soft_delete()
        self.db.commit()
        return {"success": True, "message": "消息已删除"}

    def send_overdue_reminders(self, admin_id: int) -> dict:
        """发送逾期提醒 — 查询逾期记录并给每个用户推送消息"""
        from backend.domain.borrow.repository import BorrowRecordRepository
        from backend.domain.message.models import SystemMessage
        from backend.domain.book.models import Book
        from backend.domain.child.models import Child

        borrow_repo = BorrowRecordRepository(self.db)
        overdue_records = borrow_repo.get_overdue_records()

        # 按用户去重
        user_records = {}
        for record in overdue_records:
            if record.child_id not in user_records:
                user_records[record.child_id] = []
            user_records[record.child_id].append(record)

        sent_count = 0
        for child_id, records in user_records.items():
            child = (
                self.db.query(Child)
                .filter(Child.id == child_id, Child.is_deleted == 0)
                .first()
            )
            if not child or not child.user_id:
                continue

            book_titles = []
            for r in records:
                book = self.db.query(Book).filter(Book.id == r.book_id).first()
                if book:
                    book_titles.append(book.title)

            title = "借阅逾期提醒"
            content = (
                f"您的孩子有 {len(records)} 本图书已逾期："
                f"{'、'.join(book_titles[:3])}{'等' if len(book_titles) > 3 else ''}，请尽快归还。"
            )

            msg = SystemMessage(
                user_id=child.user_id,
                title=title,
                content=content,
                msg_type=2,  # 提醒类
                priority=2,  # 高优先级
            )
            self.db.add(msg)
            sent_count += 1

        self.db.commit()
        self.system_service.write_operation_log(
            admin_id=admin_id,
            module="borrow",
            operation="send_overdue_reminders",
            content=f"发送了 {sent_count} 条逾期提醒",
        )
        return {"success": True, "sent_count": sent_count}
