# backend/domain/reading/service.py
"""阅读域业务逻辑 — 进度管理、会话记录、自动打卡"""

import logging
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.common.base_repo import BaseRepository
from backend.common.events import CheckInEvent, ReadingBookFinishedEvent, ReadingSessionCompletedEvent, event_bus
from backend.common.config_service import ConfigService
from backend.domain.child.models import Child
from backend.domain.reading.models import (
    CheckIn,
    ReadingProgress,
    ReadingSession,
    VoiceRecording,
)
from backend.domain.reading.repository import (
    BookPageRepository,
    ReadingProgressRepository,
    ReadingSessionRepository,
    CheckInRepository,
    VoiceRecordingRepository,
)
from backend.domain.reading.schemas import (
    BookPageResponse,
    ProgressResponse,
    SaveProgressRequest,
    StartSessionRequest,
    EndSessionRequest,
    SessionResponse,
    CheckInResponse,
    StreakResponse,
    SaveRecordingRequest,
    VoiceRecordingResponse,
    VoiceRecordingDetailResponse,
)

logger = logging.getLogger(__name__)

CHECKIN_MIN_MINUTES_DEFAULT = 10


class ReadingService:
    """阅读服务

    架构意图：
      - 进度管理 + 会话管理在此服务内闭环
      - 打卡通过事件总线发布 CheckInEvent
      - 连续打卡天数更新通过事件处理器处理（child 域订阅）
    """

    def __init__(self, db: Session):
        self.db = db
        self.page_repo = BookPageRepository(db)
        self.progress_repo = ReadingProgressRepository(db)
        self.session_repo = ReadingSessionRepository(db)
        self.checkin_repo = CheckInRepository(db)
        self.voice_repo = VoiceRecordingRepository(db)

    # ==================== 图书内容 ====================

    def get_book_pages(self, book_id: int) -> list[BookPageResponse]:
        return [
            BookPageResponse.model_validate(p)
            for p in self.page_repo.get_by_book(book_id)
        ]

    def get_book_page(self, book_id: int, page_number: int) -> BookPageResponse | None:
        page = self.page_repo.get_page(book_id, page_number)
        return BookPageResponse.model_validate(page) if page else None

    # ==================== 阅读进度 ====================

    def get_progress(self, child_id: int, book_id: int) -> ProgressResponse | None:
        progress = self.progress_repo.get_by_child_and_book(child_id, book_id)
        return ProgressResponse.model_validate(progress) if progress else None

    def save_progress(
        self, child_id: int, data: SaveProgressRequest
    ) -> ProgressResponse:
        """保存或更新阅读进度"""
        progress = (
            self.db.query(ReadingProgress)
            .filter(
                ReadingProgress.child_id == child_id,
                ReadingProgress.book_id == data.book_id,
                ReadingProgress.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if not progress:
            progress = ReadingProgress(
                child_id=child_id,
                book_id=data.book_id,
                current_page=data.current_page,
                total_pages=data.total_pages,
            )
            self.progress_repo.create(progress)
        else:
            progress.current_page = data.current_page
            progress.total_pages = data.total_pages

        progress.progress_pct = Decimal(
            str(round(data.current_page / max(data.total_pages, 1) * 100, 2))
        )
        progress.last_read_time = datetime.now()

        if data.current_page >= data.total_pages:
            progress.is_finished = 1
            progress.finish_time = datetime.now()

            # 读完自动创建 ReadingSubmission（自动通过，无需审核）
            # 晋级检测在 check_and_advance 中处理（需审核时会阻断）
            from backend.domain.advancement.models import ReadingSubmission
            from backend.domain.book.models import Book

            existing_sub = (
                self.db.query(ReadingSubmission)
                .filter(
                    ReadingSubmission.child_id == progress.child_id,
                    ReadingSubmission.book_id == progress.book_id,
                    ReadingSubmission.is_deleted == 0,
                )
                .first()
            )
            if not existing_sub:
                book = self.db.query(Book).filter(
                    Book.id == progress.book_id,
                    Book.is_deleted == 0,
                ).first()
                sub = ReadingSubmission(
                    child_id=progress.child_id,
                    book_id=progress.book_id,
                    word_count=book.word_count if book else 0,
                    status=ReadingSubmission.STATUS_APPROVED,
                    reviewed_at=datetime.now(),
                )
                self.db.add(sub)
                self.db.flush()

                # 自动增加已读书数 + 触发晋级检测（通过事件总线解耦）
                event_bus.publish(
                    ReadingBookFinishedEvent(
                        child_id=sub.child_id,
                        book_id=sub.book_id,
                        word_count=sub.word_count,
                    ),
                    db=self.db,
                )

        self.progress_repo.update(progress)
        self.db.commit()
        return ProgressResponse.model_validate(progress)

    def get_user_books(self, child_id: int) -> list[ProgressResponse]:
        return [
            ProgressResponse.model_validate(p)
            for p in self.progress_repo.get_by_child(child_id)
        ]

    # ==================== 阅读会话 ====================

    def start_session(
        self, child_id: int, data: StartSessionRequest
    ) -> SessionResponse:
        # 试读限制检查
        from backend.common.config_service import ConfigService
        from backend.common.types import MemberStatus
        from backend.domain.child.models import Child

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if child and child.status == MemberStatus.TRIAL:
            enabled = ConfigService.get_bool(self.db, "enable_trial_reading", True)
            if enabled:
                trial_pages = ConfigService.get_int(self.db, "trial_pages", 10)
                total_pages = (
                    self.db.query(func.sum(ReadingSession.pages_read))
                    .filter(
                        ReadingSession.child_id == child_id,
                        ReadingSession.is_deleted == 0,
                    )
                    .scalar()
                    or 0
                )
                if total_pages >= trial_pages:
                    from backend.common.exceptions import ForbiddenError

                    raise ForbiddenError(
                        f"试读用户最多阅读 {trial_pages} 页，请升级会员继续"
                    )

        session = ReadingSession(
            child_id=child_id,
            book_id=data.book_id,
            start_time=datetime.now(),
        )
        created = self.session_repo.create(session)
        self.db.commit()
        return SessionResponse.model_validate(created)

    def end_session(self, session_id: int, data: EndSessionRequest) -> SessionResponse:
        from backend.domain.reading.models import ReadingSession
        session = (
            self.db.query(ReadingSession)
            .filter(ReadingSession.id == session_id, ReadingSession.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not session:
            from backend.common.exceptions import NotFoundError
            raise NotFoundError("阅读会话不存在")
        session.end_time = datetime.now()
        session.duration_seconds = int(
            (session.end_time - session.start_time).total_seconds()
        )
        session.pages_read = data.pages_read
        session.words_read = data.words_read
        self.session_repo.update(session)

        # 自动打卡检查
        self._check_auto_checkin(
            session.child_id, session.duration_seconds, data.words_read
        )

        # 更新孩子阅读统计（累计阅读时长，通过事件总线解耦）
        event_bus.publish(
            ReadingSessionCompletedEvent(
                child_id=session.child_id,
                duration_minutes=session.duration_seconds // 60,
            ),
            db=self.db,
        )

        self.db.commit()
        return SessionResponse.model_validate(session)

    # ==================== 打卡 ====================

    def _check_auto_checkin(
        self, child_id: int, duration_seconds: int, words_read: int
    ):
        """自动打卡：阅读满10分钟（仅观察期/正式会员）"""
        from backend.common.types import MemberStatus

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if not child or child.status not in (
            MemberStatus.OBSERVATION,
            MemberStatus.OFFICIAL,
        ):
            return

        today = date.today()
        existing = self.checkin_repo.get_today_checkin(child_id, today)
        if existing:
            return

        # 每日打卡次数限制
        daily_limit = ConfigService.get_int(self.db, "daily_checkin_limit", 1)
        today_count = self.checkin_repo.count_today_checkins(child_id, today)
        if today_count >= daily_limit:
            return

        minutes = duration_seconds // 60
        min_minutes = ConfigService.get_int(
            self.db, "checkin_min_minutes", CHECKIN_MIN_MINUTES_DEFAULT
        )
        # 最低生词数检查
        min_vocab = ConfigService.get_int(self.db, "checkin_min_vocab", 5)
        if minutes >= min_minutes and words_read >= min_vocab:
            checkin = CheckIn(
                child_id=child_id,
                check_date=today,
                check_type=CheckIn.TYPE_READING,
                reading_minutes=minutes,
                words_read=words_read,
            )
            self.checkin_repo.create(checkin)
            # 发布打卡事件
            event_bus.publish(
                CheckInEvent(child_id=child_id, streak_days=0), db=self.db
            )
            logger.info(f"Auto checkin: child={child_id}, minutes={minutes}")

    def get_checkin_calendar(
        self, child_id: int, year: int, month: int
    ) -> list[CheckInResponse]:
        return [
            CheckInResponse.model_validate(c)
            for c in self.checkin_repo.get_monthly(child_id, year, month)
        ]

    def get_streak(self, child_id: int) -> StreakResponse:
        child_repo = BaseRepository(self.db, Child)
        child = child_repo.get_by_id(child_id)
        if not child:
            return StreakResponse(current_streak=0, longest_streak=0)
        return StreakResponse(
            current_streak=child.current_streak_days or 0,
            longest_streak=child.longest_streak_days or 0,
        )

    # ==================== 语音朗读 ====================

    def save_recording(self, data: SaveRecordingRequest) -> VoiceRecordingResponse:
        """保存语音录音"""
        recording = VoiceRecording(
            child_id=data.child_id,
            book_id=data.book_id,
            page_id=data.page_id,
            text_content=data.text,
            audio_url=data.audio_url,
            duration_seconds=data.duration,
        )
        created = self.voice_repo.create(recording)
        self.db.commit()
        logger.info(f"Voice recorded: child={data.child_id}, duration={data.duration}s")
        return VoiceRecordingResponse(
            id=created.id,
            audio_url=created.audio_url,
            duration_seconds=created.duration_seconds,
        )

    def get_recordings(
        self, child_id: int, book_id: int | None = None,
        page: int = 1, page_size: int = 20
    ) -> list[VoiceRecordingDetailResponse]:
        """获取语音录音列表"""
        recordings = self.voice_repo.get_by_child_and_book(child_id, book_id, page=page, page_size=page_size)
        result = []
        for r in recordings:
            result.append(
                VoiceRecordingDetailResponse(
                    id=r.id,
                    book_id=r.book_id,
                    text_content=r.text_content,
                    audio_url=r.audio_url,
                    duration_seconds=r.duration_seconds,
                    pronunciation_score=float(r.pronunciation_score)
                    if r.pronunciation_score
                    else None,
                    create_time=r.create_time,
                )
            )
        return result
