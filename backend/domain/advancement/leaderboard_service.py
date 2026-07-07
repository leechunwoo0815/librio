# backend/domain/advancement/leaderboard_service.py
"""排行榜服务 — 独立查询域，无写操作

从 AdvancementService 拆出，降低主 Service 复杂度。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.advancement.models import ChildLevel, ReadingSubmission
from backend.domain.advancement.schemas import LeaderboardEntryResponse
from backend.domain.child.models import Child

logger = logging.getLogger(__name__)


class LeaderboardService:
    """排行榜服务"""

    _PERIOD_MAP = {
        "7d": 7,
        "15d": 15,
        "30d": 30,
        "month": None,
        "year": None,
        "total": None,
    }
    _MEDAL_EMOJI = ["\U0001f947", "\U0001f948", "\U0001f949"]

    def __init__(self, db: Session):
        self.db = db
        self.child_repo = BaseRepository(db, Child)

    def get_leaderboard(
        self,
        period: str = "total",
        level_id: Optional[int] = None,
        month: Optional[int] = None,
        year: Optional[int] = None,
        limit: int = 20,
    ) -> list[LeaderboardEntryResponse]:
        """获取排行榜"""
        if period == "total":
            return self._total_leaderboard(level_id, limit)
        elif period == "month":
            if not year or not month:
                now = datetime.now()
                year, month = now.year, now.month
            return self._period_leaderboard(year, month, level_id, limit)
        elif period == "year":
            if not year:
                year = datetime.now().year
            return self._year_leaderboard(year, level_id, limit)
        else:
            days = self._PERIOD_MAP.get(period, 7)
            return self._days_leaderboard(days, level_id, limit)

    def _format_name(self, child: Child) -> str:
        name_part = child.name or ""
        en_part = child.english_name or ""
        return f"{name_part} {en_part}".strip()

    def _total_leaderboard(
        self,
        level_id: Optional[int] = None,
        limit: int = 20,
    ) -> list[LeaderboardEntryResponse]:
        """累计排行榜"""
        q = self.db.query(Child).filter(
            Child.is_deleted == 0,
            Child.total_words_read > 0,
        )
        if level_id:
            cl = self.db.query(ChildLevel.child_id).filter(
                ChildLevel.level_id == level_id
            )
            q = q.filter(Child.id.in_(cl))
        children = q.order_by(Child.total_words_read.desc()).limit(limit).all()

        result = []
        for i, child in enumerate(children):
            result.append(
                {
                    "rank": i + 1,
                    "child_id": child.id,
                    "display_name": self._format_name(child),
                    "total_words": child.total_words_read,
                    "total_books": child.total_books_finished,
                    "streak_days": child.current_streak_days,
                    "medal": self._MEDAL_EMOJI[i] if i < 3 else None,
                }
            )
        return result

    def _days_leaderboard(
        self,
        days: int,
        level_id: Optional[int] = None,
        limit: int = 20,
    ) -> list[LeaderboardEntryResponse]:
        """近N天排行榜"""
        cutoff = datetime.now() - timedelta(days=days)
        deduped = (
            self.db.query(
                ReadingSubmission.child_id,
                ReadingSubmission.book_id,
                func.max(ReadingSubmission.word_count).label("book_words"),
            )
            .filter(
                ReadingSubmission.status == ReadingSubmission.STATUS_APPROVED,
                ReadingSubmission.submitted_at >= cutoff,
            )
            .group_by(ReadingSubmission.child_id, ReadingSubmission.book_id)
            .subquery()
        )

        q = self.db.query(
            deduped.c.child_id,
            func.sum(deduped.c.book_words).label("total_words"),
        ).group_by(deduped.c.child_id)

        if level_id:
            cl = self.db.query(ChildLevel.child_id).filter(
                ChildLevel.level_id == level_id
            )
            q = q.filter(deduped.c.child_id.in_(cl))

        rows = q.order_by(func.sum(deduped.c.book_words).desc()).limit(limit).all()

        child_ids = [cid for cid, _ in rows]
        children = (
            {
                c.id: c
                for c in self.db.query(Child).filter(Child.id.in_(child_ids)).all()
            }
            if child_ids
            else {}
        )

        result = []
        for i, (child_id, total_words) in enumerate(rows):
            child = children.get(child_id)
            if child:
                result.append(
                    {
                        "rank": i + 1,
                        "child_id": child_id,
                        "display_name": self._format_name(child),
                        "total_words": total_words or 0,
                        "medal": self._MEDAL_EMOJI[i] if i < 3 else None,
                    }
                )
        return result

    def _period_leaderboard(
        self,
        year: int,
        month: int,
        level_id: Optional[int] = None,
        limit: int = 20,
    ) -> list[LeaderboardEntryResponse]:
        """月排行榜"""
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        deduped = (
            self.db.query(
                ReadingSubmission.child_id,
                ReadingSubmission.book_id,
                func.max(ReadingSubmission.word_count).label("book_words"),
            )
            .filter(
                ReadingSubmission.status == ReadingSubmission.STATUS_APPROVED,
                ReadingSubmission.submitted_at >= start,
                ReadingSubmission.submitted_at < end,
            )
            .group_by(ReadingSubmission.child_id, ReadingSubmission.book_id)
            .subquery()
        )

        q = self.db.query(
            deduped.c.child_id,
            func.sum(deduped.c.book_words).label("total_words"),
        ).group_by(deduped.c.child_id)

        rows = q.order_by(func.sum(deduped.c.book_words).desc()).limit(limit).all()

        child_ids = [cid for cid, _ in rows]
        children = (
            {
                c.id: c
                for c in self.db.query(Child).filter(Child.id.in_(child_ids)).all()
            }
            if child_ids
            else {}
        )

        result = []
        for i, (child_id, total_words) in enumerate(rows):
            child = children.get(child_id)
            if child:
                result.append(
                    {
                        "rank": i + 1,
                        "child_id": child_id,
                        "display_name": self._format_name(child),
                        "total_words": total_words or 0,
                        "medal": self._MEDAL_EMOJI[i] if i < 3 else None,
                    }
                )
        return result

    def _year_leaderboard(
        self,
        year: int,
        level_id: Optional[int] = None,
        limit: int = 20,
    ) -> list[LeaderboardEntryResponse]:
        """年排行榜"""
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)

        deduped = (
            self.db.query(
                ReadingSubmission.child_id,
                ReadingSubmission.book_id,
                func.max(ReadingSubmission.word_count).label("book_words"),
            )
            .filter(
                ReadingSubmission.status == ReadingSubmission.STATUS_APPROVED,
                ReadingSubmission.submitted_at >= start,
                ReadingSubmission.submitted_at < end,
            )
            .group_by(ReadingSubmission.child_id, ReadingSubmission.book_id)
            .subquery()
        )

        q = self.db.query(
            deduped.c.child_id,
            func.sum(deduped.c.book_words).label("total_words"),
        ).group_by(deduped.c.child_id)

        rows = q.order_by(func.sum(deduped.c.book_words).desc()).limit(limit).all()

        child_ids = [cid for cid, _ in rows]
        children = (
            {
                c.id: c
                for c in self.db.query(Child).filter(Child.id.in_(child_ids)).all()
            }
            if child_ids
            else {}
        )

        result = []
        for i, (child_id, total_words) in enumerate(rows):
            child = children.get(child_id)
            if child:
                result.append(
                    {
                        "rank": i + 1,
                        "child_id": child_id,
                        "display_name": self._format_name(child),
                        "total_words": total_words or 0,
                        "medal": self._MEDAL_EMOJI[i] if i < 3 else None,
                    }
                )
        return result
