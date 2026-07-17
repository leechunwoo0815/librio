"""Tests for 4 new API routes added in CI full-coverage sprint (2026-07-17)"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.common.types import DepositStatus, BorrowStatus


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_user(db, openid="parent1", phone="13800138001"):
    from backend.domain.user.models import User

    user = User(openid=openid, phone=phone, parent_name="测试家长")
    db.add(user)
    db.flush()
    return user


def _create_child(db, user, name="测试孩子", status=2):
    from backend.domain.child.models import Child

    child = Child(
        user_id=user.id,
        name=name,
        age=6,
        grade="一年级",
        status=status,
        deposit_status=DepositStatus.PAID,
    )
    db.add(child)
    db.flush()
    return child


def _create_book(db, title="测试图书", theme="文学"):
    from backend.domain.book.models import Book

    book = Book(
        title=title,
        author="测试作者",
        isbn=f"978{hash(title) % 10**10:010d}",
        ar_value=3.5,
        age_min=6,
        age_max=12,
        theme=theme,
        total_pages=100,
        word_count=5000,
        is_published=1,
    )
    db.add(book)
    db.flush()
    return book


# ══════════════════════════════════════════════════════════════
# 1. GET /child/transfer/records
# ══════════════════════════════════════════════════════════════


class TestGetTransferRecords:
    def test_returns_records_for_current_user(self, db):
        from backend.domain.child.service import ChildService
        from backend.domain.child.benefit_transfer_model import (
            BenefitTransferApplication,
        )

        svc = ChildService(db)
        user = _create_user(db)
        src = _create_child(db, user, "源孩子")
        tgt = _create_child(db, user, "目标孩子")

        app = BenefitTransferApplication(
            source_child_id=src.id,
            target_child_id=tgt.id,
            user_id=user.id,
            status=0,
        )
        db.add(app)
        db.commit()

        records = svc.get_transfer_records(user.id)
        assert len(records) == 1
        assert records[0]["source_child_name"] == "源孩子"
        assert records[0]["target_child_name"] == "目标孩子"
        assert records[0]["status"] == "pending"

    def test_other_user_records_not_included(self, db):
        from backend.domain.child.service import ChildService
        from backend.domain.child.benefit_transfer_model import (
            BenefitTransferApplication,
        )

        svc = ChildService(db)
        user1 = _create_user(db, openid="p1", phone="13800138001")
        user2 = _create_user(db, openid="p2", phone="13800138002")
        src = _create_child(db, user1, "源孩子")
        tgt = _create_child(db, user1, "目标孩子")

        app = BenefitTransferApplication(
            source_child_id=src.id,
            target_child_id=tgt.id,
            user_id=user1.id,
            status=0,
        )
        db.add(app)
        db.commit()

        records = svc.get_transfer_records(user2.id)
        assert len(records) == 0

    def test_empty_when_no_records(self, db):
        from backend.domain.child.service import ChildService

        svc = ChildService(db)
        user = _create_user(db)
        records = svc.get_transfer_records(user.id)
        assert records == []


# ══════════════════════════════════════════════════════════════
# 2. GET /book/{book_id}/related
# ══════════════════════════════════════════════════════════════


class TestGetRelatedBooks:
    def test_returns_books_with_same_theme(self, db):
        from backend.domain.book.service import BookService

        svc = BookService(db)
        book1 = _create_book(db, "书A", theme="文学")
        book2 = _create_book(db, "书B", theme="文学")
        _create_book(db, "书C", theme="科学")  # different theme

        related = svc.get_related_books(book1.id)
        related_ids = [b.id for b in related]
        assert book2.id in related_ids
        assert "书C" not in [b.title for b in related]

    def test_excludes_self(self, db):
        from backend.domain.book.service import BookService

        svc = BookService(db)
        book = _create_book(db, "孤独的书", theme="哲学")

        related = svc.get_related_books(book.id)
        assert all(b.id != book.id for b in related)

    def test_empty_when_no_related(self, db):
        from backend.domain.book.service import BookService

        svc = BookService(db)
        book = _create_book(db, "唯一的书", theme="唯一主题")

        related = svc.get_related_books(book.id)
        assert related == []

    def test_raises_on_nonexistent_book(self, db):
        from backend.domain.book.service import BookService
        from backend.common.exceptions import NotFoundError

        svc = BookService(db)
        with pytest.raises(NotFoundError):
            svc.get_related_books(99999)

    def test_respects_limit(self, db):
        from backend.domain.book.service import BookService

        svc = BookService(db)
        book = _create_book(db, "主体", theme="热门")
        for i in range(10):
            _create_book(db, f"相关{i}", theme="热门")

        related = svc.get_related_books(book.id, limit=3)
        assert len(related) <= 3


# ══════════════════════════════════════════════════════════════
# 3. GET /reading/checkin/{child_id}/records
# ══════════════════════════════════════════════════════════════


class TestGetCheckinRecords:
    def test_returns_recent_sessions(self, db):
        from backend.domain.reading.service import ReadingService

        svc = ReadingService(db)
        user = _create_user(db)
        child = _create_child(db, user)
        book = _create_book(db)

        from backend.domain.reading.models import ReadingSession
        from datetime import datetime

        session = ReadingSession(
            child_id=child.id,
            book_id=book.id,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_seconds=300,
            pages_read=15,
        )
        db.add(session)
        db.commit()

        records = svc.get_checkin_records(child.id)
        assert len(records) == 1
        assert records[0]["book_name"] == "测试图书"
        assert records[0]["pages"] == "15页"

    def test_empty_when_no_sessions(self, db):
        from backend.domain.reading.service import ReadingService

        svc = ReadingService(db)
        user = _create_user(db)
        child = _create_child(db, user)

        records = svc.get_checkin_records(child.id)
        assert records == []

    def test_limits_results(self, db):
        from backend.domain.reading.service import ReadingService
        from backend.domain.reading.models import ReadingSession
        from datetime import datetime

        svc = ReadingService(db)
        user = _create_user(db)
        child = _create_child(db, user)
        book = _create_book(db)

        for i in range(5):
            session = ReadingSession(
                child_id=child.id,
                book_id=book.id,
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=100,
                pages_read=5,
            )
            db.add(session)
        db.commit()

        records = svc.get_checkin_records(child.id, limit=3)
        assert len(records) == 3


# ══════════════════════════════════════════════════════════════
# 4. DELETE /child/{child_id}
# ══════════════════════════════════════════════════════════════


class TestDeleteChild:
    def test_soft_delete_child(self, db):
        from backend.domain.child.service import ChildService

        svc = ChildService(db)
        user = _create_user(db)
        child = _create_child(db, user)

        result = svc.delete_child(child.id, user.id)
        assert result["success"] is True

        from backend.domain.child.models import Child

        deleted = db.query(Child).filter(Child.id == child.id).first()
        assert deleted.is_deleted == 1

    def test_raises_when_active_borrows_exist(self, db):
        from backend.domain.child.service import ChildService
        from backend.common.exceptions import ValidationError
        from backend.domain.borrow.models import BorrowRecord
        from datetime import datetime

        svc = ChildService(db)
        user = _create_user(db)
        child = _create_child(db, user)
        book = _create_book(db)

        borrow = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            status=BorrowStatus.BORROWING,
            borrow_time=datetime.now(),
            due_date=datetime.now(),
        )
        db.add(borrow)
        db.commit()

        with pytest.raises(ValidationError, match="未还书"):
            svc.delete_child(child.id, user.id)

    def test_raises_on_nonexistent_child(self, db):
        from backend.domain.child.service import ChildService
        from backend.common.exceptions import NotFoundError

        svc = ChildService(db)
        user = _create_user(db)
        with pytest.raises(NotFoundError):
            svc.delete_child(99999, user.id)

    def test_raises_on_other_users_child(self, db):
        from backend.domain.child.service import ChildService
        from backend.common.exceptions import ForbiddenError

        svc = ChildService(db)
        user1 = _create_user(db, openid="p1", phone="13800138001")
        user2 = _create_user(db, openid="p2", phone="13800138002")
        child = _create_child(db, user1)

        with pytest.raises(ForbiddenError):
            svc.delete_child(child.id, user2.id)
