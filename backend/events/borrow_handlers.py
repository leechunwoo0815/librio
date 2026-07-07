# backend/events/borrow_handlers.py
"""借阅/预约相关事件处理器"""

import logging
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.types import BookCopyStatus
from backend.domain.book.models import BookCopy, Book

logger = logging.getLogger(__name__)


def handle_book_borrowed_for_copy_status(event, db: Session):
    """借书 → 更新 BookCopy 状态"""
    if event.book_copy_id:
        copy_repo = BaseRepository(db, BookCopy)
        copy = copy_repo.get_by_id(event.book_copy_id)
        if copy:
            copy.status = BookCopyStatus.BORROWED
            copy_repo.update(copy)


def handle_book_returned_for_copy_status(event, db: Session):
    """还书 → 更新 BookCopy 状态 + 释放库存（单次 flush 保证原子性）"""
    try:
        if event.book_copy_id:
            copy_repo = BaseRepository(db, BookCopy)
            copy = copy_repo.get_by_id(event.book_copy_id)
            if copy:
                copy.status = BookCopyStatus.AVAILABLE

        book_repo = BaseRepository(db, Book)
        book = book_repo.get_by_id(event.book_id)
        if book:
            book.available_stock = (book.available_stock or 0) + 1

        # 单次 flush 确保两个更新在同一事务中
        db.flush()
    except Exception as e:
        logger.error(f"handle_book_returned_for_copy_status failed: {e}")
        raise


def handle_reservation_created_for_stock(event, db: Session):
    """预约创建 → 扣减库存"""
    from backend.domain.book.service import BookService

    service = BookService(db)
    service.decrease_available_stock(event.book_id)


def handle_reservation_expired_for_stock(event, db: Session):
    """预约过期 → 释放库存"""
    from backend.domain.book.service import BookService

    service = BookService(db)
    service.increase_available_stock(event.book_id)


def handle_reservation_fulfilled_for_borrow(event, db: Session):
    """预约取书 → 自动创建借阅记录"""
    from backend.domain.borrow.service import BorrowService

    service = BorrowService(db)
    service.borrow_from_reservation(event.child_id, event.book_id, event.reservation_id)


def handle_book_overdue_for_fines(event, db: Session):
    """图书逾期 → 记录日志（罚款由 scheduler mark_overdue_books 统一计算）"""
    logger.info(
        f"Book overdue: child_id={event.child_id}, book_id={event.book_id}, "
        f"borrow_record_id={event.borrow_record_id}, days={event.overdue_days}"
    )
