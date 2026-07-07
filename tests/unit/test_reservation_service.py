# tests/unit/test_reservation_service.py
"""预约域单元测试"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.reservation.models import Reservation
from backend.domain.reservation.service import ReservationService
from backend.domain.reservation.schemas import ReservationCreateRequest
from backend.common.types import DepositStatus, ReservationStatus
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
    user = User(openid="test_res", phone="13800138040")
    db.add(user); db.commit()
    child = Child(user_id=user.id, name="预约测试", age=7, grade="二年级",
                  status=Child.STATUS_OFFICIAL, deposit_status=DepositStatus.PAID)
    db.add(child); db.commit()
    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=3.2, age_min=7, age_max=9, word_count=31000,
                total_stock=5, available_stock=5, offline_available=1)
    db.add(book); db.commit()
    return user, child, book


def test_create_reservation(db):
    """成功预约"""
    user, child, book = _setup(db)
    svc = ReservationService(db)
    result = svc.create_reservation(ReservationCreateRequest(child_id=child.id, book_id=book.id))
    assert result.status == ReservationStatus.PENDING


def test_create_reservation_no_stock(db):
    """库存不足不可预约"""
    user, child, book = _setup(db)
    book.available_stock = 0
    db.commit()
    svc = ReservationService(db)
    with pytest.raises(Exception, match="库存"):
        svc.create_reservation(ReservationCreateRequest(child_id=child.id, book_id=book.id))


def test_create_reservation_locks_stock(db):
    """预约锁定库存"""
    user, child, book = _setup(db)
    initial_stock = book.available_stock
    svc = ReservationService(db)
    svc.create_reservation(ReservationCreateRequest(child_id=child.id, book_id=book.id))
    db.refresh(book)
    assert book.available_stock == initial_stock - 1


def test_expire_reservation_releases_stock(db):
    """过期释放库存"""
    user, child, book = _setup(db)
    svc = ReservationService(db)
    result = svc.create_reservation(ReservationCreateRequest(child_id=child.id, book_id=book.id))
    db.refresh(book)
    stock_after_reserve = book.available_stock
    svc.expire_reservation(result.id)
    db.refresh(book)
    assert book.available_stock == stock_after_reserve + 1


def test_get_child_reservations(db):
    """获取预约列表"""
    user, child, book = _setup(db)
    svc = ReservationService(db)
    svc.create_reservation(ReservationCreateRequest(child_id=child.id, book_id=book.id))
    reservations = svc.get_child_reservations(child.id)
    assert len(reservations) >= 1
