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
            .first()
        )
        if entry:
            entry.status = BookshelfStatus.FINISHED
            shelf_repo.update(entry)
    except Exception as e:
        logger.warning(f"handle_quiz_passed_for_bookshelf skipped: {e}")


def handle_quiz_passed_for_submission(event, db: Session):
    """测验通过 → 阅读提交保持待审核状态（由老师手动审核）"""
    # P0-9 修复：不再自动批准提交，由老师通过 review_submission 审核
    # 审核通过时会触发 increment_books_read + check_and_advance
    pass


def handle_quiz_failed_for_logging(event, db: Session = None):
    """测验未通过 → 记录日志"""
    logger.info(
        f"Quiz failed: child_id={event.child_id}, book_id={event.book_id}, "
        f"quiz_id={event.quiz_id}, score={event.score}"
    )
