# backend/domain/reading/repository.py
"""阅读域数据访问层"""

from datetime import date

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.reading.models import (
    BookPage,
    ReadingProgress,
    ReadingSession,
    CheckIn,
    VoiceRecording,
)


class BookPageRepository(BaseRepository[BookPage]):
    def __init__(self, db: Session):
        super().__init__(db, BookPage)

    def get_by_book(self, book_id: int) -> list[BookPage]:
        return (
            self.db.query(BookPage)
            .filter(
                BookPage.book_id == book_id,
                BookPage.is_deleted == 0,
            )
            .order_by(BookPage.page_number)
            .all()
        )

    def get_page(self, book_id: int, page_number: int) -> BookPage | None:
        return (
            self.db.query(BookPage)
            .filter(
                BookPage.book_id == book_id,
                BookPage.page_number == page_number,
                BookPage.is_deleted == 0,
            )
            .first()
        )


class ReadingProgressRepository(BaseRepository[ReadingProgress]):
    def __init__(self, db: Session):
        super().__init__(db, ReadingProgress)

    def get_by_child_and_book(
        self, child_id: int, book_id: int
    ) -> ReadingProgress | None:
        return (
            self.db.query(ReadingProgress)
            .filter(
                ReadingProgress.child_id == child_id,
                ReadingProgress.book_id == book_id,
            )
            .first()
        )

    def get_by_child(self, child_id: int) -> list[ReadingProgress]:
        return (
            self.db.query(ReadingProgress)
            .filter(
                ReadingProgress.child_id == child_id,
            )
            .order_by(ReadingProgress.last_read_time.desc())
            .all()
        )


class ReadingSessionRepository(BaseRepository[ReadingSession]):
    def __init__(self, db: Session):
        super().__init__(db, ReadingSession)


class CheckInRepository(BaseRepository[CheckIn]):
    def __init__(self, db: Session):
        super().__init__(db, CheckIn)

    def get_today_checkin(self, child_id: int, today: date) -> CheckIn | None:
        return (
            self.db.query(CheckIn)
            .filter(
                CheckIn.child_id == child_id,
                CheckIn.check_date == today,
            )
            .first()
        )

    def count_today_checkins(self, child_id: int, today: date) -> int:
        return (
            self.db.query(CheckIn)
            .filter(
                CheckIn.child_id == child_id,
                CheckIn.check_date == today,
            )
            .count()
        )

    def get_monthly(self, child_id: int, year: int, month: int) -> list[CheckIn]:
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return (
            self.db.query(CheckIn)
            .filter(
                CheckIn.child_id == child_id,
                CheckIn.check_date >= start,
                CheckIn.check_date < end,
            )
            .all()
        )


class VoiceRecordingRepository(BaseRepository[VoiceRecording]):
    def __init__(self, db: Session):
        super().__init__(db, VoiceRecording)

    def get_by_child_and_book(
        self, child_id: int, book_id: int | None = None
    ) -> list[VoiceRecording]:
        """获取孩子的语音记录"""
        q = self.db.query(VoiceRecording).filter(
            VoiceRecording.child_id == child_id,
            VoiceRecording.is_deleted == 0,
        )
        if book_id:
            q = q.filter(VoiceRecording.book_id == book_id)
        return q.order_by(VoiceRecording.create_time.desc()).all()
