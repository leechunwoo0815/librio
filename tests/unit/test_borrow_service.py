# tests/unit/test_borrow_service.py
"""借阅域单元测试"""

import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.borrow.models import BorrowRecord
from backend.domain.borrow.service import BorrowService
from backend.domain.borrow.schemas import BorrowBookRequest, ReturnBookRequest
from backend.common.types import BorrowStatus, DepositStatus
from backend.bootstrap import register_event_handlers


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


def _setup(db):
    user = User(openid="test_borrow", phone="13800138020")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="借阅测试",
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
        deposit_status=DepositStatus.PAID,
    )
    db.add(child)
    db.commit()
    book = Book(
        isbn="9780064400558",
        title="Charlotte's Web",
        author="E.B. White",
        ar_value=Decimal("3.2"),
        age_min=7,
        age_max=9,
        word_count=31000,
        total_stock=5,
        available_stock=5,
        price=Decimal("80"),
    )
    db.add(book)
    db.commit()
    return user, child, book


def test_borrow_book_success(db):
    user, child, book = _setup(db)
    svc = BorrowService(db)
    result = svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=book.id))
    assert result.status == BorrowStatus.BORROWING


def test_borrow_book_no_deposit(db):
    user, child, book = _setup(db)
    child.deposit_status = DepositStatus.UNPAID
    db.commit()
    svc = BorrowService(db)
    with pytest.raises(Exception, match="押金"):
        svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=book.id))


def test_borrow_book_expired_child(db):
    user, child, book = _setup(db)
    child.status = Child.STATUS_EXPIRED
    db.commit()
    svc = BorrowService(db)
    with pytest.raises(Exception):
        svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=book.id))


def test_borrow_book_duplicate(db):
    user, child, book = _setup(db)
    svc = BorrowService(db)
    svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=book.id))
    with pytest.raises(Exception, match="已借阅"):
        svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=book.id))


def test_return_book(db):
    user, child, book = _setup(db)
    svc = BorrowService(db)
    borrow_result = svc.borrow_book(
        BorrowBookRequest(child_id=child.id, book_id=book.id)
    )
    return_result = svc.return_book(
        ReturnBookRequest(borrow_record_id=borrow_result.id)
    )
    assert return_result.status == BorrowStatus.RETURNED
    assert return_result.return_time is not None


def test_return_book_releases_stock(db):
    user, child, book = _setup(db)
    svc = BorrowService(db)
    initial_stock = book.available_stock
    borrow_result = svc.borrow_book(
        BorrowBookRequest(child_id=child.id, book_id=book.id)
    )
    db.refresh(book)
    assert book.available_stock == initial_stock - 1
    svc.return_book(ReturnBookRequest(borrow_record_id=borrow_result.id))
    db.refresh(book)
    assert book.available_stock == initial_stock


def test_borrow_limit_includes_overdue(db):
    user, child, book = _setup(db)
    svc = BorrowService(db)
    for i in range(20):
        b = Book(
            isbn=f"978{i:010d}",
            title=f"Book{i}",
            author="A",
            ar_value=Decimal("2.0"),
            age_min=5,
            age_max=9,
            word_count=1000,
            total_stock=1,
            available_stock=1,
        )
        db.add(b)
        db.commit()
        svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=b.id))
    records = (
        db.query(BorrowRecord)
        .filter(
            BorrowRecord.child_id == child.id,
            BorrowRecord.status == BorrowStatus.BORROWING,
        )
        .all()
    )
    for r in records[:5]:
        r.status = BorrowStatus.OVERDUE
    db.commit()
    extra = Book(
        isbn="978EXTRA001",
        title="Extra",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=1000,
        total_stock=1,
        available_stock=1,
    )
    db.add(extra)
    db.commit()
    with pytest.raises(Exception, match="借阅上限"):
        svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=extra.id))


def test_get_child_borrows(db):
    user, child, book = _setup(db)
    svc = BorrowService(db)
    svc.borrow_book(BorrowBookRequest(child_id=child.id, book_id=book.id))
    records, total = svc.get_child_borrows(child.id)
    assert total == 1
    assert records[0].book_id == book.id
