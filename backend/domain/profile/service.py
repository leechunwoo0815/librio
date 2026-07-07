# backend/domain/profile/service.py
"""名片域业务逻辑 — 聚合其他域数据生成阅读名片"""

import logging
from sqlalchemy.orm import Session
from backend.common.base_repo import BaseRepository
from backend.domain.child.models import Child
from backend.domain.advancement.models import (
    ChildLevel,
    Level,
    ChildAchievement,
    Achievement,
)

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.child_repo = BaseRepository(db, Child)

    def get_profile(self, child_id: int) -> dict | None:
        child = self.child_repo.get_by_id(child_id)
        if not child:
            return None

        # 当前级别
        cl = (
            self.db.query(ChildLevel)
            .filter(ChildLevel.child_id == child_id, ChildLevel.is_current)
            .first()
        )
        level_info = None
        if cl:
            level = self.db.query(Level).filter(Level.id == cl.level_id).first()
            if level:
                level_info = {
                    "level_id": level.id,
                    "level_name": level.name,
                    "badge_emoji": level.badge_emoji,
                }

        # 成就
        cas = (
            self.db.query(ChildAchievement)
            .filter(ChildAchievement.child_id == child_id)
            .all()
        )
        achievements = []
        for ca in cas:
            ach = (
                self.db.query(Achievement)
                .filter(Achievement.id == ca.achievement_id)
                .first()
            )
            if ach:
                achievements.append({"name": ach.name, "badge_emoji": ach.badge_emoji})

        return {
            "child_id": child.id,
            "name": child.name,
            "english_name": child.english_name,
            "age": child.age,
            "grade": child.grade,
            "total_books_finished": child.total_books_finished or 0,
            "total_words_read": child.total_words_read or 0,
            "total_reading_minutes": child.total_reading_minutes or 0,
            "current_streak_days": child.current_streak_days or 0,
            "longest_streak_days": child.longest_streak_days or 0,
            "current_level": level_info,
            "achievement_count": len(achievements),
            "achievements": achievements,
        }
