# backend/tasks/jobs/borrow_overdue.py
"""借阅逾期检测定时任务"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def check():
    """检查借阅逾期：标记逾期状态 + 发布事件"""
    from backend.database import get_session
    from backend.domain.borrow.models import BorrowRecord
    from backend.common.types import BorrowStatus
    from backend.common.events import event_bus, BookOverdueEvent

    db = get_session()
    try:
        now = datetime.now()
        overdue_records = (
            db.query(BorrowRecord)
            .filter(
                BorrowRecord.status == BorrowStatus.BORROWING,
                BorrowRecord.due_date < now,
                BorrowRecord.is_deleted == 0,
            )
            .all()
        )

        for record in overdue_records:
            record.status = BorrowStatus.OVERDUE
            record.overdue_days = (now - record.due_date).days

            event_bus.publish(
                BookOverdueEvent(
                    child_id=record.child_id,
                    book_id=record.book_id,
                    borrow_record_id=record.id,
                    overdue_days=record.overdue_days,
                ),
                db=db,
            )

            logger.info(
                f"BORROW_OVERDUE: id={record.id}, child={record.child_id}, "
                f"book={record.book_id}, overdue_days={record.overdue_days}"
            )

        if overdue_records:
            db.commit()
            logger.info(f"Borrow overdue check: {len(overdue_records)} records overdue")
        logger.info("Borrow overdue check completed")
    except Exception as e:
        db.rollback()
        logger.error(f"Borrow overdue check failed: {e}", exc_info=True)
    finally:
        db.close()
