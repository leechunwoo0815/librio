"""
F-035 终审同类漏改闭环：月报平台统计三处（top_books/quiz_pass_rate/refund_rate）
必须使用 < next_month_start 而非 <= last_month_end（date 午夜会漏掉月末当天记录）。
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.tasks.scheduler as scheduler
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.advancement.models import Quiz
from backend.domain.book.models import Book
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_user(db, openid, phone, create_time):
    u = User(openid=openid, phone=phone, create_time=create_time)
    db.add(u)
    db.commit()
    return u


def _mk_child(db, user, name):
    c = Child(
        user_id=user.id,
        name=name,
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
    )
    db.add(c)
    db.commit()
    return c


def _mk_book(db, title, isbn):
    b = Book(
        isbn=isbn,
        title=title,
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
    )
    db.add(b)
    db.commit()
    return b


class TestF035MonthEndBoundary:
    def test_month_end_records_are_counted(self, db, monkeypatch):
        """月末当天（23:59:59）创建的用户/订单/测评/借阅必须计入上月统计"""
        month_end = datetime(2026, 7, 31, 23, 59, 59)
        next_day = datetime(2026, 8, 1, 0, 0, 0)

        user_old = _mk_user(db, "f035a", "13800000351", month_end)
        _mk_user(db, "f035b", "13800000352", next_day)
        child = _mk_child(db, user_old, "F035")
        book = _mk_book(db, "月末书", "9780000000351")

        order_old = Order(
            order_no="F035-001",
            user_id=user_old.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500.00"),
            pay_status=PayStatus.PAID,
            pay_time=month_end,
            create_time=month_end,
            refund_status=2,  # REFUND_DONE
        )
        db.add(order_old)
        db.commit()

        quiz_old = Quiz(
            child_id=child.id,
            book_id=book.id,
            status=Quiz.STATUS_COMPLETED,
            total_questions=1,
            correct_count=1,
            score=Decimal("100"),
            create_time=month_end,
        )
        db.add(quiz_old)
        db.commit()

        br_old = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            borrow_time=month_end,
            due_date=month_end + timedelta(days=21),
            status=1,
            create_time=month_end,
        )
        db.add(br_old)
        db.commit()

        # 下月 0 点记录（不得计入上月）
        order_new = Order(
            order_no="F035-002",
            user_id=user_old.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500.00"),
            pay_status=PayStatus.PAID,
            pay_time=next_day,
            create_time=next_day,
            refund_status=0,
        )
        db.add(order_new)
        br_new = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            borrow_time=next_day,
            due_date=next_day + timedelta(days=21),
            status=1,
            create_time=next_day,
        )
        db.add(br_new)
        db.commit()

        captured = {}

        def fake_info(msg, *args, **kwargs):
            if isinstance(msg, str) and msg.startswith("MONTHLY_PLATFORM_STATS"):
                captured["stats"] = msg

        monkeypatch.setattr(scheduler.logger, "info", fake_info)
        monkeypatch.setattr(
            scheduler,
            "date",
            type("D", (), {"today": staticmethod(lambda: date(2026, 8, 1))}),
        )
        monkeypatch.setattr(scheduler, "_get_db_session", lambda: db)

        scheduler.generate_monthly_reports()

        stats = captured.get("stats")
        assert stats is not None, "未捕获月报平台统计日志"
        assert "new_users=1" in stats, stats
        assert "quiz_pass_rate=100.0%" in stats, stats
        assert "refund_rate=100.0%" in stats, stats
        assert "top_books=['月末书(1)']" in stats, stats
