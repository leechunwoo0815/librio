# backend/domain/borrow/repository.py
"""借阅域数据访问层"""

from datetime import datetime

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.types import BorrowStatus
from backend.domain.borrow.models import BorrowRecord


class BorrowRecordRepository(BaseRepository[BorrowRecord]):
    def __init__(self, db: Session):
        super().__init__(db, BorrowRecord)

    def get_active_by_child(self, child_id: int) -> list[BorrowRecord]:
        """获取孩子当前借阅中的记录"""
        return self.list_all(limit=50, child_id=child_id, status=BorrowStatus.BORROWING)

    def count_active(self, child_id: int) -> int:
        """统计孩子当前借阅数量（含逾期）"""
        return (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )

    def get_by_child_and_book(
        self, child_id: int, book_id: int, status: int | None = None
    ) -> BorrowRecord | None:
        """查询孩子对某本书的借阅记录"""
        q = self.db.query(BorrowRecord).filter(
            BorrowRecord.child_id == child_id,
            BorrowRecord.book_id == book_id,
            BorrowRecord.is_deleted == 0,
        )
        if status is not None:
            q = q.filter(BorrowRecord.status == status)
        return q.first()

    def get_overdue_records(self) -> list[BorrowRecord]:
        """获取所有逾期未还的借阅记录"""
        return (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.due_date < datetime.now(),
                BorrowRecord.is_deleted == 0,
                BorrowRecord.overdue_reminded == 0,  # F-098：已提醒过不再重复
            )
            .with_for_update()  # F-098 终审：双管理员并发点击防双发（标记与查询同事务）
            .all()
        )
