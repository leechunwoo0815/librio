# tests/unit/test_waitlist.py
"""F4 等候名单 + B4 取书提醒单元测试

- 库存 0 可加入等候；有库存不可（应直接预约）；重复等候拦截
- 库存释放（预约过期/取消/还书）自动通知队首（事件链，先到先得）
- 成功预约自动关闭活跃等候
- B4：到期前 24h 未取 → scheduler 提醒一次（不重复）
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
import backend.domain.message.models  # noqa: F401 — 注册 system_message 表
import backend.domain.admin.models  # noqa: F401 — teacher_message FK → teacher 表
from backend.bootstrap import register_event_handlers
from backend.common.exceptions import ConflictError, ValidationError
from backend.domain.book.models import Book
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.reservation.models import BookWaitlist, Reservation
from backend.domain.reservation.schemas import ReservationCreateRequest
from backend.domain.reservation.service import ReservationService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


def _mk(db, stock=0):
    user = User(openid="wl1", phone="13800000301")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="等候", age=7, grade="二年级", status=2)
    db.add(child)
    db.commit()
    book = Book(
        isbn="WL001",
        title="热门绘本",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=1000,
        total_stock=1,
        available_stock=stock,
        offline_available=1,
    )
    db.add(book)
    db.commit()
    return user, child, book


class TestJoinWaitlist:
    def test_join_when_out_of_stock(self, db):
        _, child, book = _mk(db, stock=0)
        svc = ReservationService(db)
        result = svc.join_waitlist(child.id, book.id)
        assert result["success"] is True
        entry = db.query(BookWaitlist).filter_by(child_id=child.id).one()
        assert entry.status == BookWaitlist.STATUS_WAITING

    def test_join_rejected_when_in_stock(self, db):
        _, child, book = _mk(db, stock=2)
        svc = ReservationService(db)
        with pytest.raises(ValidationError, match="有库存"):
            svc.join_waitlist(child.id, book.id)

    def test_duplicate_join_rejected(self, db):
        _, child, book = _mk(db, stock=0)
        svc = ReservationService(db)
        svc.join_waitlist(child.id, book.id)
        with pytest.raises(ConflictError, match="已在等候名单"):
            svc.join_waitlist(child.id, book.id)

    def test_join_rejected_when_already_reserved(self, db):
        _, child, book = _mk(db, stock=0)
        r = Reservation(
            child_id=child.id,
            book_id=book.id,
            status=0,
            expire_time=datetime.now() + timedelta(hours=70),
        )
        db.add(r)
        db.commit()
        svc = ReservationService(db)
        with pytest.raises(ConflictError, match="已预约"):
            svc.join_waitlist(child.id, book.id)


class TestWaitlistNotify:
    def test_expire_releases_stock_and_notifies(self, db):
        """预约过期释放库存 → 事件链自动通知队首"""
        user, child, book = _mk(db, stock=0)
        svc = ReservationService(db)
        svc.join_waitlist(child.id, book.id)

        # 另一孩子的预约过期
        user2 = User(openid="wl2", phone="13800000302")
        db.add(user2)
        db.commit()
        child2 = Child(user_id=user2.id, name="另一", age=8, grade="三年级", status=2)
        db.add(child2)
        db.commit()
        reservation = Reservation(
            child_id=child2.id,
            book_id=book.id,
            status=0,
            expire_time=datetime.now() - timedelta(hours=1),
        )
        db.add(reservation)
        db.commit()

        svc.expire_reservation(reservation.id)
        db.commit()

        entry = db.query(BookWaitlist).filter_by(child_id=child.id).one()
        assert entry.status == BookWaitlist.STATUS_NOTIFIED
        assert entry.notify_time is not None
        msg = (
            db.query(SystemMessage)
            .filter_by(user_id=user.id, title="您等候的图书到货啦")
            .first()
        )
        assert msg is not None

    def test_first_come_first_served(self, db):
        """先到先得：先加入的队首被通知"""
        user, child, book = _mk(db, stock=0)
        user2 = User(openid="wl3", phone="13800000303")
        db.add(user2)
        db.commit()
        child2 = Child(user_id=user2.id, name="后排", age=8, grade="三年级", status=2)
        db.add(child2)
        db.commit()
        svc = ReservationService(db)
        svc.join_waitlist(child.id, book.id)  # 队首
        svc.join_waitlist(child2.id, book.id)  # 队尾

        book.available_stock = 1
        db.commit()
        assert svc.notify_next_waiter(db, book.id) is True
        first = db.query(BookWaitlist).filter_by(child_id=child.id).one()
        second = db.query(BookWaitlist).filter_by(child_id=child2.id).one()
        assert first.status == BookWaitlist.STATUS_NOTIFIED
        assert second.status == BookWaitlist.STATUS_WAITING

    def test_no_notify_without_stock(self, db):
        _, child, book = _mk(db, stock=0)
        svc = ReservationService(db)
        svc.join_waitlist(child.id, book.id)
        assert svc.notify_next_waiter(db, book.id) is False

    def test_reservation_closes_waitlist(self, db):
        """成功预约 → 活跃等候自动成交"""
        _, child, book = _mk(db, stock=1)
        svc = ReservationService(db)
        # 先有等候（库存曾为0）
        entry = BookWaitlist(child_id=child.id, book_id=book.id)
        db.add(entry)
        db.commit()
        svc.create_reservation(
            ReservationCreateRequest(child_id=child.id, book_id=book.id)
        )
        db.refresh(entry)
        assert entry.status == BookWaitlist.STATUS_FULFILLED


class TestPickupReminder:
    def test_remind_within_24h_once(self, db):
        """B4：24h 内到期未取 → 提醒一次；再次执行不重复"""
        from backend.tasks.scheduler import remind_reservation_pickup

        user, child, book = _mk(db, stock=1)
        reservation = Reservation(
            child_id=child.id,
            book_id=book.id,
            status=0,
            expire_time=datetime.now() + timedelta(hours=12),
        )
        db.add(reservation)
        db.commit()

        remind_reservation_pickup(db)
        db.refresh(reservation)
        assert reservation.pickup_reminded == 1
        assert (
            db.query(SystemMessage)
            .filter_by(user_id=user.id, title="预约取书提醒")
            .count()
            == 1
        )

        # 再次执行：已提醒，不重复
        remind_reservation_pickup(db)
        assert (
            db.query(SystemMessage)
            .filter_by(user_id=user.id, title="预约取书提醒")
            .count()
            == 1
        )

    def test_no_remind_beyond_24h(self, db):
        from backend.tasks.scheduler import remind_reservation_pickup

        _, child, book = _mk(db, stock=1)
        reservation = Reservation(
            child_id=child.id,
            book_id=book.id,
            status=0,
            expire_time=datetime.now() + timedelta(hours=60),
        )
        db.add(reservation)
        db.commit()

        remind_reservation_pickup(db)
        db.refresh(reservation)
        assert reservation.pickup_reminded == 0
