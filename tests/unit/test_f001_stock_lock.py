# tests/unit/test_f001_stock_lock.py
"""F-001/004 库存读-改-写行锁回归测试

9 处写点全部加 with_for_update（deposit mark_book_lost / damage 5 处 / book add_copy /
admin batch_generate / admin 状态流转重算）。SQLite 行锁 no-op，单测验证行为不变；
并发串行化由 scripts/verify_mysql_concurrency.py 场景 F 实证（RED total=1 → GREEN total=0）。
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.database import Base
from backend.domain.book.models import Book, BookCopy
from backend.domain.book.service import BookService
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.service import DepositService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_book_and_borrow(db, total=2):
    user = User(openid="f001user", phone="13800000101")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="F001", age=7, grade="二年级")
    db.add(child)
    db.commit()
    book = Book(
        title="库存书",
        author="A",
        isbn=f"978{abs(hash('f001')) % 10**13:013d}",
        total_stock=total,
        available_stock=total,
        offline_available=1,
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=500,
    )
    db.add(book)
    db.flush()
    copy = BookCopy(book_id=book.id, barcode=f"BK-{abs(hash('f001c')) % 10**8}", status=0)
    db.add(copy)
    db.flush()
    br = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        book_copy_id=copy.id,
        borrow_time=datetime.now() - timedelta(days=10),
        due_date=datetime.now() - timedelta(days=5),
        status=0,
    )
    db.add(br)
    db.commit()
    return book, br


class TestF001StockLock:
    def test_mark_book_lost_decrements_once(self, db):
        book, br = _mk_book_and_borrow(db)
        DepositService(db).mark_book_lost(br.id, admin_id=1)
        db.refresh(book)
        assert book.total_stock == 1
        assert book.available_stock == 1

    def test_add_copy_increments(self, db):
        book, _ = _mk_book_and_borrow(db, total=1)
        BookService(db).create_book_copy_admin(book.id, barcode=None)
        db.refresh(book)
        assert book.total_stock == 2
        assert book.available_stock == 2
