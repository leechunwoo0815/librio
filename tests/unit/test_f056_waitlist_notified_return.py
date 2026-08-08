"""F-056 回归：候补 NOTIFIED 通知超时未抢到 → 允许重新排队

原缺陷（R6 F4）：notify_next_waiter 置 NOTIFIED 后无任何回退机制，
通知未抢到者被永久静默失格（不可再通知、不可重新加入，仅可手动取消）。
修复：join_waitlist 对 NOTIFIED 且 notify_time 超过配置阈值者自动转回 WAITING 重新排队。
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.admin.models  # noqa: F401
import backend.domain.message.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.exceptions import ConflictError
from backend.database import Base
from backend.domain.admin.models import SystemConfig
from backend.domain.book.models import Book
from backend.domain.child.models import Child
from backend.domain.reservation.models import BookWaitlist
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


def _mk_notified(db, notify_age_hours: float) -> tuple[User, Child, Book, BookWaitlist]:
    user = User(openid="f056", phone="13800005600")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="候补", age=7, grade="二年级")
    db.add(child)
    db.commit()
    book = Book(
        isbn="F056001",
        title="候补书",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        total_stock=1,
        available_stock=0,
        offline_available=1,
    )
    db.add(book)
    db.commit()
    entry = BookWaitlist(
        child_id=child.id,
        book_id=book.id,
        status=BookWaitlist.STATUS_NOTIFIED,
        notify_time=datetime.now() - timedelta(hours=notify_age_hours),
    )
    db.add(entry)
    db.commit()
    return user, child, book, entry


class TestF056NotifiedReturn:
    def test_expired_notified_requeues(self, db):
        """通知超 48h 未抢到：重新排队（status→WAITING，记录复用）"""
        user, child, book, entry = _mk_notified(db, notify_age_hours=49)
        svc = ReservationService(db)

        result = svc.join_waitlist(child.id, book.id)

        assert result["success"] is True
        assert result["waitlist_id"] == entry.id
        db.refresh(entry)
        assert entry.status == BookWaitlist.STATUS_WAITING

    def test_fresh_notified_still_rejected(self, db):
        """通知未超 48h：仍在名单中，不得重复加入"""
        user, child, book, entry = _mk_notified(db, notify_age_hours=1)
        svc = ReservationService(db)

        with pytest.raises(ConflictError, match="已在等候名单"):
            svc.join_waitlist(child.id, book.id)

    def test_notified_without_time_not_expired(self, db):
        """NOTIFIED 但 notify_time 为空（异常数据）：保守拒绝，不自动重排"""
        user, child, book, entry = _mk_notified(db, notify_age_hours=0)
        entry.notify_time = None
        db.commit()
        svc = ReservationService(db)

        with pytest.raises(ConflictError, match="已在等候名单"):
            svc.join_waitlist(child.id, book.id)

    def test_configured_ttl_controls_requeue(self, db):
        """配置 waitlist_notified_ttl_hours=1：2 小时前通知即视为超时可重排"""
        user, child, book, entry = _mk_notified(db, notify_age_hours=2)
        db.add(
            SystemConfig(
                config_key="waitlist_notified_ttl_hours",
                config_value="1",
                config_type="int",
            )
        )
        db.commit()
        svc = ReservationService(db)

        result = svc.join_waitlist(child.id, book.id)
        assert result["success"] is True
        db.refresh(entry)
        assert entry.status == BookWaitlist.STATUS_WAITING
