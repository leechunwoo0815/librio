# tests/unit/test_reading_overdue_audio.py
"""逾期音频锁定单元测试 — 反向排查 P0-1"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.borrow.models import BorrowRecord
from backend.domain.reading.models import BookPage
from backend.domain.reading.service import ReadingService
from backend.common.types import BorrowStatus
from backend.common.exceptions import ForbiddenError


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def setup_data(db):
    """创建用户、孩子、图书、页面"""
    user = User(openid="test_overdue_audio", phone="13800138031")
    db.add(user)
    db.commit()

    child = Child(
        user_id=user.id,
        name="音频测试",
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
    )
    db.add(child)

    book = Book(
        isbn="978999001",
        title="测试音频书",
        author="测试",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        word_count=500,
        has_audio=True,
        audio_url="/audio/test.mp3",
    )
    db.add(book)
    db.commit()

    page1 = BookPage(
        book_id=book.id,
        page_number=1,
        content_type=0,
        text_content="Page 1 text",
        audio_url="/audio/p1.mp3",
    )
    page2 = BookPage(
        book_id=book.id,
        page_number=2,
        content_type=0,
        text_content="Page 2 text",
        audio_url="/audio/p2.mp3",
    )
    db.add(page1)
    db.add(page2)
    db.commit()

    return user, child, book


class TestOverdueAudioLock:
    """逾期音频锁定测试"""

    def test_get_pages_no_overdue(self, db, setup_data):
        """正常借阅 — 返回页面列表"""
        _, child, book = setup_data
        svc = ReadingService(db)

        pages = svc.get_book_pages(book.id, child.id)
        assert len(pages) == 2
        assert pages[0].audio_url is not None

    def test_get_pages_with_overdue(self, db, setup_data):
        """有逾期借阅 — 抛 ForbiddenError"""
        _, child, book = setup_data

        # 创建逾期借阅记录
        borrow = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            status=BorrowStatus.OVERDUE,
            borrow_time=datetime.now() - timedelta(days=30),
            due_date=datetime.now() - timedelta(days=9),
        )
        db.add(borrow)
        db.commit()

        svc = ReadingService(db)
        with pytest.raises(ForbiddenError, match="借阅已逾期"):
            svc.get_book_pages(book.id, child.id)

    def test_get_pages_no_child_id(self, db, setup_data):
        """不传 child_id — 不做校验，正常返回"""
        _, _, book = setup_data
        svc = ReadingService(db)

        pages = svc.get_book_pages(book.id)  # no child_id
        assert len(pages) == 2

    def test_get_pages_overdue_different_book(self, db, setup_data):
        """逾期书 A → 锁全部音频（查任何书都 403）"""
        _, child, book = setup_data

        book2 = Book(
            isbn="978999002",
            title="另一本书",
            author="测试",
            ar_value=1.5,
            age_min=5,
            age_max=9,
            word_count=300,
        )
        db.add(book2)
        db.commit()

        # 对 book 逾期
        borrow = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            status=BorrowStatus.OVERDUE,
            borrow_time=datetime.now() - timedelta(days=30),
            due_date=datetime.now() - timedelta(days=9),
        )
        db.add(borrow)
        db.commit()

        svc = ReadingService(db)
        # 查另一本书也 403（逾期即全锁）
        with pytest.raises(ForbiddenError, match="借阅已逾期"):
            svc.get_book_pages(book2.id, child.id)

    def test_get_pages_borrowing_not_overdue(self, db, setup_data):
        """有借阅中但未逾期 — 正常返回"""
        _, child, book = setup_data

        borrow = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            status=BorrowStatus.BORROWING,
            borrow_time=datetime.now() - timedelta(days=1),
            due_date=datetime.now() + timedelta(days=20),
        )
        db.add(borrow)
        db.commit()

        svc = ReadingService(db)
        pages = svc.get_book_pages(book.id, child.id)
        assert len(pages) == 2
