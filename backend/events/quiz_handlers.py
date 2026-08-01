# backend/events/quiz_handlers.py
"""测验相关事件处理器"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle_quiz_passed_for_advancement(event, db: Session):
    """测验通过 → 增加测验通过数 + 晋级检测（已读书数由阅读提交审核触发）"""
    from backend.domain.advancement.service import AdvancementService

    service = AdvancementService(db)
    service.increment_quizzes_passed(event.child_id)
    service.check_and_advance(event.child_id)


def handle_quiz_passed_for_child_stats(event, db: Session):
    """测验通过 → 更新孩子阅读统计（仅词数，不增已读书数）"""
    from backend.domain.child.service import ChildService

    service = ChildService(db)
    service.update_reading_stats(event.child_id, words=event.word_count, books=0)


def handle_quiz_passed_for_borrow(event, db: Session):
    """测验通过 → 标记借阅记录的 quiz_passed（失败不影响主流程）"""
    try:
        from backend.domain.borrow.service import BorrowService

        service = BorrowService(db)
        service.mark_quiz_passed(event.child_id, event.book_id)
    except Exception as e:
        logger.warning(f"handle_quiz_passed_for_borrow skipped: {e}")


def handle_quiz_passed_for_bookshelf(event, db: Session):
    """测验通过 → 更新书架状态为已读完（失败不影响主流程）"""
    try:
        from backend.domain.bookshelf.models import Bookshelf
        from backend.common.base_repo import BaseRepository
        from backend.common.types import BookshelfStatus

        shelf_repo = BaseRepository(db, Bookshelf)
        entry = (
            db.query(Bookshelf)
            .filter(
                Bookshelf.child_id == event.child_id,
                Bookshelf.book_id == event.book_id,
                Bookshelf.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if entry:
            entry.status = BookshelfStatus.FINISHED
            shelf_repo.update(entry)
    except Exception as e:
        logger.warning(f"handle_quiz_passed_for_bookshelf skipped: {e}")


def handle_quiz_passed_for_submission(event, db: Session):
    """测验通过 → 达标提交自动审核（D4：阅读≥N分钟自动 APPROVED，否则转人工队列）"""
    from datetime import datetime

    from sqlalchemy import func

    from backend.common.config_service import ConfigService
    from backend.common.events import ReadingBookFinishedEvent, event_bus
    from backend.domain.advancement.models import ReadingSubmission
    from backend.domain.reading.models import ReadingSession

    if not ConfigService.get_bool(db, "submission_auto_approve", True):
        return

    sub = (
        db.query(ReadingSubmission)
        .filter(
            ReadingSubmission.child_id == event.child_id,
            ReadingSubmission.book_id == event.book_id,
            ReadingSubmission.status == ReadingSubmission.STATUS_PENDING,
            ReadingSubmission.is_deleted == 0,
        )
        .order_by(ReadingSubmission.create_time)
        .with_for_update()
        .first()
    )
    if not sub:
        return

    min_minutes = ConfigService.get_int(db, "submission_min_minutes", 10)
    total_seconds = (
        db.query(func.coalesce(func.sum(ReadingSession.duration_seconds), 0))
        .filter(
            ReadingSession.child_id == event.child_id,
            ReadingSession.book_id == event.book_id,
            ReadingSession.is_deleted == 0,
        )
        .scalar()
        or 0
    )
    if total_seconds < min_minutes * 60:
        logger.info(
            f"D4: submission {sub.id} 阅读时长不足 "
            f"({total_seconds}s < {min_minutes}min)，转人工审核队列"
        )
        return

    sub.status = ReadingSubmission.STATUS_APPROVED
    sub.reviewed_at = datetime.now()
    event_bus.publish(
        ReadingBookFinishedEvent(
            child_id=event.child_id,
            book_id=event.book_id,
            word_count=sub.word_count or event.word_count,
        ),
        db=db,
    )
    logger.info(f"D4: submission {sub.id} auto-approved on quiz pass")


def handle_quiz_failed_for_logging(event, db: Session = None):
    """测验未通过 → 记录日志"""
    logger.info(
        f"Quiz failed: child_id={event.child_id}, book_id={event.book_id}, "
        f"quiz_id={event.quiz_id}, score={event.score}"
    )
