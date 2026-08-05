# tests/unit/test_fulfill_barcode.py
"""B1a：扫码取书（barcode fulfill）— 副本级借阅 + 异常拦截"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.common.types import (
    BookCopyStatus,
    DepositStatus,
    MemberStatus,
    ReservationStatus,
)
from backend.common.exceptions import ConflictError, NotFoundError, ValidationError
from backend.domain.book.models import Book, BookCopy
from backend.domain.child.models import Child
from backend.domain.reservation.models import Reservation
from backend.domain.reservation.schemas import ReservationFulfillRequest
from backend.domain.reservation.service import ReservationService
from backend.domain.user.models import User


@pytest.fixture
def db():
    _ = Book, BookCopy, Child, User, Reservation
    from backend.events.registry import register_event_handlers

    register_event_handlers()  # fulfill → 事件链创建借阅记录依赖 handler 注册
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def seed(db):
    user = User(id=1, phone="13800000001", parent_name="家长", openid="op_b1", status=1)
    db.add(user)
    child = Child(
        id=1,
        user_id=1,
        name="小明",
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
        deposit_status=DepositStatus.PAID,
        member_expire_time=datetime.now() + timedelta(days=300),
    )
    db.add(child)
    book = Book(
        id=1,
        isbn="978B1000001",
        title="B1 Book",
        author="A",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        word_count=1000,
        total_stock=2,
        available_stock=2,
        offline_available=1,
        price=50,
    )
    db.add(book)
    copy = BookCopy(
        id=1, book_id=1, barcode="BC-B1-001", status=BookCopyStatus.AVAILABLE
    )
    db.add(copy)
    res = Reservation(
        id=1,
        child_id=1,
        book_id=1,
        status=ReservationStatus.PENDING,
        expire_time=datetime.now() + timedelta(hours=72),
    )
    db.add(res)
    db.commit()
    return {"child": child, "book": book, "copy": copy, "res": res}


class TestFulfillWithBarcode:
    def test_barcode_fulfill_binds_copy(self, db, seed):
        """扫码取书：借阅记录精确到副本"""
        svc = ReservationService(db)
        resp = svc.fulfill_reservation(
            ReservationFulfillRequest(reservation_id=1, barcode="BC-B1-001")
        )
        assert resp.status == ReservationStatus.FULFILLED
        from backend.domain.borrow.models import BorrowRecord

        record = db.query(BorrowRecord).filter(BorrowRecord.child_id == 1).first()
        assert record is not None
        assert record.book_copy_id == 1

    def test_barcode_not_found(self, db, seed):
        svc = ReservationService(db)
        with pytest.raises(NotFoundError, match="不存在"):
            svc.fulfill_reservation(
                ReservationFulfillRequest(reservation_id=1, barcode="NOPE-999")
            )

    def test_barcode_book_mismatch(self, db, seed):
        book2 = Book(
            id=2,
            isbn="978B1000002",
            title="Other",
            author="A",
            ar_value=2.0,
            age_min=5,
            age_max=9,
            word_count=1000,
            total_stock=1,
            available_stock=1,
            price=50,
        )
        db.add(book2)
        db.add(BookCopy(id=2, book_id=2, barcode="BC-B1-002", status=0))
        db.commit()
        svc = ReservationService(db)
        with pytest.raises(ValidationError, match="与预约图书不符"):
            svc.fulfill_reservation(
                ReservationFulfillRequest(reservation_id=1, barcode="BC-B1-002")
            )

    def test_barcode_copy_not_available(self, db, seed):
        seed["copy"].status = BookCopyStatus.MAINTENANCE
        db.commit()
        svc = ReservationService(db)
        with pytest.raises(ConflictError, match="状态异常"):
            svc.fulfill_reservation(
                ReservationFulfillRequest(reservation_id=1, barcode="BC-B1-001")
            )

    def test_manual_fulfill_still_works(self, db, seed):
        """F42：手动取书（不带 barcode）强制绑定一本 AVAILABLE 副本，不再产生孤儿借阅"""
        svc = ReservationService(db)
        resp = svc.fulfill_reservation(ReservationFulfillRequest(reservation_id=1))
        assert resp.status == ReservationStatus.FULFILLED
        from backend.domain.borrow.models import BorrowRecord

        record = db.query(BorrowRecord).filter(BorrowRecord.child_id == 1).first()
        assert record is not None
        assert record.book_copy_id == 1  # F42：自动绑定可用副本，杜绝 None 孤儿

    def test_manual_fulfill_no_available_copy_rejected(self, db, seed):
        """F42：无可用副本时手动取书必须拦截（不能制造无副本借阅）"""
        seed["copy"].status = BookCopyStatus.BORROWED
        db.commit()
        svc = ReservationService(db)
        with pytest.raises(ValidationError, match="暂无可用副本"):
            svc.fulfill_reservation(ReservationFulfillRequest(reservation_id=1))

    def test_barcode_only_auto_matches_reservation(self, db, seed):
        """扫码枪流程：仅扫条码（无 reservation_id）自动匹配最早待取预约"""
        svc = ReservationService(db)
        resp = svc.fulfill_reservation(ReservationFulfillRequest(barcode="BC-B1-001"))
        assert resp.status == ReservationStatus.FULFILLED
        assert resp.id == 1
        from backend.domain.borrow.models import BorrowRecord

        record = db.query(BorrowRecord).filter(BorrowRecord.child_id == 1).first()
        assert record is not None
        assert record.book_copy_id == 1

    def test_barcode_only_no_pending_reservation(self, db, seed):
        """仅条码但该书无待取预约 → 404"""
        seed["res"].status = ReservationStatus.CANCELLED
        db.commit()
        svc = ReservationService(db)
        with pytest.raises(NotFoundError, match="没有待取预约"):
            svc.fulfill_reservation(ReservationFulfillRequest(barcode="BC-B1-001"))
