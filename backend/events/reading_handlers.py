# backend/events/reading_handlers.py
"""阅读相关事件处理器"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle_book_finished_for_advancement(event, db: Session):
    """读完一本书 → 增加已读书数 + 触发晋级检测"""
    from backend.domain.advancement.service import AdvancementService

    service = AdvancementService(db)
    service.increment_books_read(event.child_id)
    service.check_and_advance(event.child_id)


def handle_session_completed_for_child_stats(event, db: Session):
    """阅读会话结束 → 更新孩子阅读统计（累计时长）"""
    from backend.domain.child.service import ChildService

    service = ChildService(db)
    service.update_reading_stats(event.child_id, minutes=event.duration_minutes)
