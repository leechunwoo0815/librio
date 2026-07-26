# tests/unit/test_borrow_copy_status.py
"""P1：副本状态借书拦截 — §7.3 四条异常（已借出/维修/报废/损坏/丢失不可借）"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.common.types import BookCopyStatus, DepositStatus, MemberStatus
from backend.common.exceptions import ConflictError
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.domain.borrow.service import BorrowService
from backend.domain.borrow.schemas import BorrowBookRequest
from backend.domain.child.models import Child
from backend.domain.user.models import User


@pytest.fixture
def db():
    # 注册模型
    _ = Book, BookCopy, BorrowRecord, Child, User
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def child(db):
    user = User(
        id=1,
        phone="13800000001",
        parent_name="家长",
        openid="openid_p1",
        status=User.STATUS_ACTIVE,
    )
    db.add(user)
    c = Child(
        id=1,
        user_id=1,
        name="小明",
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
        deposit_status=DepositStatus.PAID,
        member_expire_time=datetime.now() + timedelta(days=300),
    )
    db.add(c)
    db.commit()
    return c


def _make_book_with_copy(db, copy_status, barcode="BC-P1-001"):
    book = Book(
        isbn="978P1000001",
        title="P1 Book",
        author="A",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        word_count=1000,
        total_stock=1,
        available_stock=1,
        price=50,
    )
    db.add(book)
    db.flush()
    copy = BookCopy(book_id=book.id, barcode=barcode, status=copy_status)
    db.add(copy)
    db.commit()
    return book, copy


class TestCopyStatusBorrowBlock:
    """各异常状态副本借书应被拦截（P1 修复）"""

    def test_available_copy_can_borrow(self, db, child):
        book, copy = _make_book_with_copy(db, BookCopyStatus.AVAILABLE)
        svc = BorrowService(db)
        resp = svc.borrow_book(
            BorrowBookRequest(child_id=child.id, book_id=book.id, book_copy_id=copy.id)
        )
        assert resp.id is not None

    def test_borrowed_copy_blocked_with_due_date(self, db, child):
        book, copy = _make_book_with_copy(db, BookCopyStatus.BORROWED)
        # 副本当前被另一孩子借出
        other = Child(
            id=2,
            user_id=1,
            name="小红",
            age=6,
            grade="一年级",
            status=MemberStatus.OFFICIAL,
            deposit_status=DepositStatus.PAID,
        )
        db.add(other)
        db.add(
            BorrowRecord(
                child_id=2,
                book_id=book.id,
                book_copy_id=copy.id,
                borrow_time=datetime.now(),
                due_date=datetime(2026, 8, 1),
                status=0,
            )
        )
        db.commit()
        svc = BorrowService(db)
        with pytest.raises(
            ConflictError, match="该书已被借出，预计归还日期：2026-08-01"
        ):
            svc.borrow_book(
                BorrowBookRequest(
                    child_id=child.id, book_id=book.id, book_copy_id=copy.id
                )
            )

    def test_maintenance_copy_blocked(self, db, child):
        book, copy = _make_book_with_copy(db, BookCopyStatus.MAINTENANCE)
        svc = BorrowService(db)
        with pytest.raises(ConflictError, match="该书正在维修中，暂时无法借阅"):
            svc.borrow_book(
                BorrowBookRequest(
                    child_id=child.id, book_id=book.id, book_copy_id=copy.id
                )
            )

    def test_scrapped_copy_blocked(self, db, child):
        book, copy = _make_book_with_copy(db, BookCopyStatus.SCRAPPED)
        svc = BorrowService(db)
        with pytest.raises(ConflictError, match="该书已报废，无法借阅"):
            svc.borrow_book(
                BorrowBookRequest(
                    child_id=child.id, book_id=book.id, book_copy_id=copy.id
                )
            )

    def test_damaged_copy_blocked(self, db, child):
        book, copy = _make_book_with_copy(db, BookCopyStatus.DAMAGED)
        svc = BorrowService(db)
        with pytest.raises(ConflictError, match="该书已损坏，无法借阅"):
            svc.borrow_book(
                BorrowBookRequest(
                    child_id=child.id, book_id=book.id, book_copy_id=copy.id
                )
            )

    def test_lost_copy_blocked(self, db, child):
        book, copy = _make_book_with_copy(db, BookCopyStatus.LOST)
        svc = BorrowService(db)
        with pytest.raises(ConflictError, match="该书已丢失，无法借阅"):
            svc.borrow_book(
                BorrowBookRequest(
                    child_id=child.id, book_id=book.id, book_copy_id=copy.id
                )
            )
