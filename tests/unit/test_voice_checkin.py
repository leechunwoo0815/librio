"""语音朗读打卡测试 — 跟进项1：朗读完成后触发每日打卡"""

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.common.base_model import BaseModel
from backend.common.types import MemberStatus
from backend.domain.child.models import Child
from backend.domain.reading.models import CheckIn
from backend.domain.reading.service import ReadingService
from backend.domain.reading.schemas import SaveRecordingRequest


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    BaseModel.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def reading_service(db_session):
    return ReadingService(db_session)


def _create_child(db: Session, status: int = MemberStatus.OFFICIAL) -> Child:
    child = Child(
        user_id=1,
        name="Test Child",
        age=8,
        grade="G2",
        status=status,
    )
    db.add(child)
    db.flush()
    return child


def _create_book(db, child):
    from backend.domain.book.models import Book

    book = Book(
        title="Test Book",
        author="Author",
        isbn="1234567890",
        ar_value=Decimal("2.5"),
        age_min=3,
        age_max=15,
        total_stock=5,
        available_stock=5,
        price=Decimal("50.00"),
        word_count=500,
    )
    db.add(book)
    db.flush()
    return book


class TestVoiceCheckin:
    """语音朗读自动打卡测试"""

    def test_voice_recording_creates_checkin(self, db_session, reading_service):
        """朗读完成 → 自动创建打卡记录"""
        child = _create_child(db_session)
        book = _create_book(db_session, child)

        data = SaveRecordingRequest(
            child_id=child.id,
            book_id=book.id,
            text="Hello world",
            audio_url="http://example.com/audio.mp3",
            duration=30,
        )
        result = reading_service.save_recording(data)

        assert result.id > 0
        # 验证打卡记录已创建
        checkin = (
            db_session.query(CheckIn)
            .filter(
                CheckIn.child_id == child.id,
                CheckIn.check_date == date.today(),
            )
            .first()
        )
        assert checkin is not None
        assert checkin.check_type == CheckIn.TYPE_VOICE

    def test_voice_recording_no_duplicate_checkin(self, db_session, reading_service):
        """今日已打卡 → 不再重复创建"""
        child = _create_child(db_session)
        book = _create_book(db_session, child)

        # 先手动创建一条阅读打卡
        existing = CheckIn(
            child_id=child.id,
            check_date=date.today(),
            check_type=CheckIn.TYPE_READING,
        )
        db_session.add(existing)
        db_session.flush()

        data = SaveRecordingRequest(
            child_id=child.id,
            book_id=book.id,
            text="Hello",
            audio_url="http://example.com/audio.mp3",
            duration=30,
        )
        reading_service.save_recording(data)

        # 验证只有一条打卡记录（没重复创建）
        count = (
            db_session.query(CheckIn)
            .filter(
                CheckIn.child_id == child.id,
                CheckIn.check_date == date.today(),
                CheckIn.is_deleted == 0,
            )
            .count()
        )
        assert count == 1

    def test_voice_recording_trial_no_checkin(self, db_session, reading_service):
        """体验用户 → 不创建打卡"""
        child = _create_child(db_session, status=MemberStatus.TRIAL)
        book = _create_book(db_session, child)

        data = SaveRecordingRequest(
            child_id=child.id,
            book_id=book.id,
            text="Hello",
            audio_url="http://example.com/audio.mp3",
            duration=30,
        )
        reading_service.save_recording(data)

        checkin = (
            db_session.query(CheckIn)
            .filter(
                CheckIn.child_id == child.id,
                CheckIn.check_date == date.today(),
            )
            .first()
        )
        assert checkin is None
