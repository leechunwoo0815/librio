# backend/events/misc_handlers.py
"""其他事件处理器（打卡、晋级证书）"""

import logging
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository

logger = logging.getLogger(__name__)


def handle_level_advanced_for_certificate(event, db: Session):
    """晋级 → 生成晋级证书"""
    from backend.domain.certificate.service import CertificateService

    service = CertificateService(db)
    service.create_level_certificate(event.child_id, event.to_level)


def handle_checkin_for_child_streak(event, db: Session):
    """打卡 → 更新连续打卡天数"""
    from backend.domain.child.models import Child

    child_repo = BaseRepository(db, Child)
    child = child_repo.get_by_id(event.child_id)
    if child:
        child.current_streak_days = (child.current_streak_days or 0) + 1
        if child.current_streak_days > (child.longest_streak_days or 0):
            child.longest_streak_days = child.current_streak_days
        child_repo.update(child)
