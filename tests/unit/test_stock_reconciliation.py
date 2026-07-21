"""T3.7 库存双口径对账任务测试"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.book.models import Book, BookCopy
from backend.common.types import BookCopyStatus


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _create_book(db, book_id=1, total=3, avail=2):
    book = Book(
        id=book_id,
        isbn=f"978-{book_id:013d}",
        title=f"Book {book_id}",
        author="Test",
        ar_value=1.0,
        age_min=3,
        age_max=12,
        total_stock=total,
        available_stock=avail,
    )
    db.add(book)
    db.flush()
    return book


def _create_copy(db, book_id, barcode, status, copy_id=None):
    kwargs = dict(
        book_id=book_id,
        barcode=barcode,
        status=status,
    )
    if copy_id is not None:
        kwargs["id"] = copy_id
    copy = BookCopy(**kwargs)
    db.add(copy)
    db.flush()
    return copy


def test_stock_consistent_no_change(db_session):
    """库存一致时不应修改"""
    book = _create_book(db_session, total=2, avail=1)
    _create_copy(db_session, book.id, "BC001", BookCopyStatus.AVAILABLE)
    _create_copy(db_session, book.id, "BC002", BookCopyStatus.BORROWED)
    db_session.commit()

    from backend.tasks.scheduler import reconcile_stock

    reconcile_stock(db=db_session)

    db_session.refresh(book)
    assert book.total_stock == 2
    assert book.available_stock == 1


def test_stock_fix_total_mismatch(db_session):
    """total_stock 不一致时自动修正"""
    book = _create_book(db_session, total=5, avail=2)
    _create_copy(db_session, book.id, "BC001", BookCopyStatus.AVAILABLE)
    _create_copy(db_session, book.id, "BC002", BookCopyStatus.BORROWED)
    _create_copy(db_session, book.id, "BC003", BookCopyStatus.MAINTENANCE)
    # total_stock=5 但实际有效副本只有3个
    db_session.commit()

    from backend.tasks.scheduler import reconcile_stock

    reconcile_stock(db=db_session)

    db_session.refresh(book)
    assert book.total_stock == 3  # AVAILABLE + BORROWED + MAINTENANCE
    assert book.available_stock == 1  # 只有 AVAILABLE


def test_stock_fix_available_mismatch(db_session):
    """available_stock 不一致时自动修正"""
    book = _create_book(db_session, total=3, avail=0)
    _create_copy(db_session, book.id, "BC001", BookCopyStatus.AVAILABLE)
    _create_copy(db_session, book.id, "BC002", BookCopyStatus.BORROWED)
    _create_copy(db_session, book.id, "BC003", BookCopyStatus.BORROWED)
    db_session.commit()

    from backend.tasks.scheduler import reconcile_stock

    reconcile_stock(db=db_session)

    db_session.refresh(book)
    assert book.total_stock == 3
    assert book.available_stock == 1  # 只有 1 本 AVAILABLE


def test_scrapped_not_counted_in_total(db_session):
    """SCRAPPED 副本不计入 total_stock"""
    book = _create_book(db_session, total=3, avail=1)
    _create_copy(db_session, book.id, "BC001", BookCopyStatus.AVAILABLE)
    _create_copy(db_session, book.id, "BC002", BookCopyStatus.SCRAPPED)
    _create_copy(db_session, book.id, "BC003", BookCopyStatus.SCRAPPED)
    db_session.commit()

    from backend.tasks.scheduler import reconcile_stock

    reconcile_stock(db=db_session)

    db_session.refresh(book)
    assert book.total_stock == 1
    assert book.available_stock == 1


def test_lost_not_counted_in_total(db_session):
    """LOST 副本不计入 total_stock"""
    book = _create_book(db_session, total=3, avail=1)
    _create_copy(db_session, book.id, "BC001", BookCopyStatus.AVAILABLE)
    _create_copy(db_session, book.id, "BC002", BookCopyStatus.LOST)
    _create_copy(db_session, book.id, "BC003", BookCopyStatus.LOST)
    db_session.commit()

    from backend.tasks.scheduler import reconcile_stock

    reconcile_stock(db=db_session)

    db_session.refresh(book)
    assert book.total_stock == 1
    assert book.available_stock == 1


def test_damaged_counted_in_total_but_not_available(db_session):
    """DAMAGED 计入 total_stock（可修复）但不计入 available_stock"""
    book = _create_book(db_session, total=3, avail=2)
    _create_copy(db_session, book.id, "BC001", BookCopyStatus.AVAILABLE)
    _create_copy(db_session, book.id, "BC002", BookCopyStatus.AVAILABLE)
    _create_copy(db_session, book.id, "BC003", BookCopyStatus.DAMAGED)
    db_session.commit()

    from backend.tasks.scheduler import reconcile_stock

    reconcile_stock(db=db_session)

    db_session.refresh(book)
    assert book.total_stock == 3  # AVAILABLE + AVAILABLE + DAMAGED
    assert book.available_stock == 2  # 2 AVAILABLE
