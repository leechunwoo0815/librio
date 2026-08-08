"""F-085/F-098/F-110 回归：提醒去重标记（参照 R132 pickup_reminded 范本）

三入口同一模式：查询过滤"已提醒"标记，发送/告警后置 1——
同一记录不再每日重复轰炸。F-085=scheduler 待审提醒、F-098=管理端逾期提醒、
F-110=scheduler 退款超时告警。
"""

import functools
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.admin.models  # noqa: F401
import backend.domain.message.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import BorrowStatus, PayStatus, OrderType
from backend.database import Base
from backend.domain.advancement.models import ReadingSubmission
from backend.domain.book.models import Book
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.user.models import User
from backend.tasks import scheduler


@pytest.fixture(autouse=True)
def _noop_lock(monkeypatch):
    def _noop(*args, **kwargs):
        def deco(func):
            @functools.wraps(func)
            def wrapper(*a, **kw):
                return func(*a, **kw)

            return wrapper

        return deco

    monkeypatch.setattr(scheduler, "distributed_lock", _noop)


@pytest.fixture
def db_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    monkeypatch.setattr(scheduler, "_get_db_session", lambda: session)
    yield session, Session
    session.close()


def _mk_user_child(db, suffix):
    user = User(openid=f"dedup_{suffix}", phone=f"138000{suffix}")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name=f"娃{suffix}", age=7, grade="二年级")
    db.add(child)
    db.commit()
    return user, child


def _mk_book(db):
    b = Book(
        isbn="DD-DEDUP-1",
        title="去重书",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
    )
    db.add(b)
    db.commit()
    return b


class TestF085PendingReminder:
    def test_remind_once_only(self, db_factory):
        db, Session = db_factory
        user, child = _mk_user_child(db, "085")
        child.teacher_id = 1
        db.commit()
        sub = ReadingSubmission(
            child_id=child.id,
            book_id=1,
            status=ReadingSubmission.STATUS_PENDING,
            submitted_at=datetime.now() - timedelta(days=10),
        )
        db.add(sub)
        db.commit()
        sub_id = sub.id  # 任务内 close 注入 session 后原对象 detached，先取值

        scheduler.remind_pending_submissions()
        # 任务内 commit+close 注入 session：用新 session 复核
        check = Session()
        fresh = check.query(ReadingSubmission).filter_by(id=sub_id).one()
        assert fresh.pending_reminded == 1
        assert check.query(SystemMessage).count() == 1

        # 第二次运行：已标记，不再发消息
        scheduler.remind_pending_submissions()
        check2 = Session()
        fresh2 = check2.query(ReadingSubmission).filter_by(id=sub_id).one()
        assert fresh2.pending_reminded == 1
        assert check2.query(SystemMessage).count() == 1
        check.close()
        check2.close()


class TestF098OverdueReminder:
    def test_manual_send_reminds_once(self, db_factory):
        from backend.domain.admin.services.message_service import AdminMessageService

        db, _ = db_factory
        user, child = _mk_user_child(db, "098")
        book = _mk_book(db)
        record = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            status=BorrowStatus.OVERDUE,
            borrow_time=datetime.now() - timedelta(days=30),
            due_date=datetime.now() - timedelta(days=9),
        )
        db.add(record)
        db.commit()

        svc = AdminMessageService(db)
        first = svc.send_overdue_reminders(admin_id=1)
        assert first["sent_count"] == 1
        db.refresh(record)
        assert record.overdue_reminded == 1
        assert db.query(SystemMessage).count() == 1

        # 第二次手动触发：已标记记录不再匹配
        second = svc.send_overdue_reminders(admin_id=1)
        assert second["sent_count"] == 0
        assert db.query(SystemMessage).count() == 1


class TestF110StaleRefundAlert:
    def test_alert_once_only(self, db_factory):
        db, Session = db_factory
        user, child = _mk_user_child(db, "110")
        order = Order(
            order_no="MW-DEDUP-110",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OFFICIAL_MEMBER,
            amount=Decimal("5400"),
            pay_status=PayStatus.PAID,
        )
        db.add(order)
        db.commit()
        refund = RefundApplication(
            order_id=order.id,
            child_id=child.id,
            user_id=user.id,
            refund_amount=Decimal("100"),
            status=RefundApplication.STATUS_APPROVED,
            review_time=datetime.now() - timedelta(days=10),
        )
        db.add(refund)
        db.commit()

        scheduler.alert_stale_refunds(db)
        check = Session()
        fresh = check.query(RefundApplication).filter_by(id=refund.id).one()
        assert fresh.stale_alerted == 1
        assert check.query(SystemMessage).count() == 1

        scheduler.alert_stale_refunds(db)
        check2 = Session()
        fresh2 = check2.query(RefundApplication).filter_by(id=refund.id).one()
        assert fresh2.stale_alerted == 1
        assert check2.query(SystemMessage).count() == 1
        check.close()
        check2.close()
