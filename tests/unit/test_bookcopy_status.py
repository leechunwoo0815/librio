# tests/unit/test_bookcopy_status.py
"""D02 副本维修/报废流转 — set_copy_status 单元测试"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.types import BookCopyStatus
from backend.database import Base
from backend.domain.admin.services.book_service import AdminBookService
from backend.domain.book.models import Book, BookCopy


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _make_book(db):
    b = Book(
        title=f"测试书{uuid.uuid4().hex[:4]}",
        author="测试作者",
        isbn=uuid.uuid4().hex[:13],
        ar_value=3.0,
        age_min=3,
        age_max=8,
        total_stock=3,
        available_stock=2,
    )
    db.add(b)
    db.flush()
    db.refresh(b)
    return b


def _make_copy(db, book_id, status):
    c = BookCopy(book_id=book_id, barcode=uuid.uuid4().hex[:12], status=status)
    db.add(c)
    db.flush()
    db.refresh(c)
    return c


class TestSetCopyStatus:
    def test_available_to_maintenance(self, db):
        book = _make_book(db)
        copy = _make_copy(db, book.id, BookCopyStatus.AVAILABLE)
        result = AdminBookService(db).set_copy_status(
            copy.id, BookCopyStatus.MAINTENANCE
        )
        assert result["success"] is True
        db.refresh(copy)
        db.refresh(book)
        assert copy.status == BookCopyStatus.MAINTENANCE
        assert book.total_stock == 1  # 维修仍计入 total
        assert book.available_stock == 0  # 但不计入 available

    def test_maintenance_back_to_available(self, db):
        book = _make_book(db)
        copy = _make_copy(db, book.id, BookCopyStatus.MAINTENANCE)
        AdminBookService(db).set_copy_status(copy.id, BookCopyStatus.AVAILABLE)
        db.refresh(copy)
        db.refresh(book)
        assert copy.status == BookCopyStatus.AVAILABLE
        assert book.available_stock == 1

    def test_available_to_scrapped_reduces_total(self, db):
        book = _make_book(db)
        copy = _make_copy(db, book.id, BookCopyStatus.AVAILABLE)
        AdminBookService(db).set_copy_status(copy.id, BookCopyStatus.SCRAPPED)
        db.refresh(book)
        assert book.total_stock == 0  # 报废不计入 total
        assert book.available_stock == 0

    def test_damaged_to_maintenance(self, db):
        book = _make_book(db)
        copy = _make_copy(db, book.id, BookCopyStatus.DAMAGED)
        result = AdminBookService(db).set_copy_status(
            copy.id, BookCopyStatus.MAINTENANCE
        )
        assert result["success"] is True

    def test_borrowed_blocked(self, db):
        book = _make_book(db)
        copy = _make_copy(db, book.id, BookCopyStatus.BORROWED)
        with pytest.raises(ValidationError, match="不允许流转"):
            AdminBookService(db).set_copy_status(copy.id, BookCopyStatus.MAINTENANCE)

    def test_scrapped_is_terminal(self, db):
        book = _make_book(db)
        copy = _make_copy(db, book.id, BookCopyStatus.SCRAPPED)
        with pytest.raises(ValidationError):
            AdminBookService(db).set_copy_status(copy.id, BookCopyStatus.AVAILABLE)

    def test_lost_is_terminal(self, db):
        book = _make_book(db)
        copy = _make_copy(db, book.id, BookCopyStatus.LOST)
        with pytest.raises(ValidationError):
            AdminBookService(db).set_copy_status(copy.id, BookCopyStatus.SCRAPPED)

    def test_invalid_target_status(self, db):
        book = _make_book(db)
        copy = _make_copy(db, book.id, BookCopyStatus.AVAILABLE)
        with pytest.raises(ValidationError):
            AdminBookService(db).set_copy_status(copy.id, BookCopyStatus.BORROWED)

    def test_nonexistent_copy(self, db):
        with pytest.raises(NotFoundError):
            AdminBookService(db).set_copy_status(999999, BookCopyStatus.MAINTENANCE)

    def test_stock_recount_multi_copies(self, db):
        """多副本场景：报废 1 本后 total/available 按实际计数"""
        book = _make_book(db)
        c1 = _make_copy(db, book.id, BookCopyStatus.AVAILABLE)
        _make_copy(db, book.id, BookCopyStatus.AVAILABLE)
        _make_copy(db, book.id, BookCopyStatus.BORROWED)
        AdminBookService(db).set_copy_status(c1.id, BookCopyStatus.SCRAPPED)
        db.refresh(book)
        assert book.total_stock == 2  # 在馆1 + 借出1
        assert book.available_stock == 1
