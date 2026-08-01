# tests/unit/test_fine_policy.py
"""逾期服务费策略单元测试 — B7/B8 决策

- 宽限期 overdue_grace_days（默认 3）：前 3 天免罚，第 4 天起算
- 上限 overdue_fine_cap_ratio（默认 0.5）：单本 ≤ 定价 × 0.5
- 首次免罚 first_overdue_free（默认 true）：每孩子首次逾期记录免罚
- 音频锁定：宽限期内不锁，第 4 天起锁
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.fine_policy import (
    OverduePolicy,
    apply_fine,
    calc_fine,
    calc_overdue_days,
    is_first_overdue,
)
from backend.database import Base
from backend.domain.book.models import Book
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.reading.models import BookPage
from backend.domain.reading.service import ReadingService
from backend.domain.user.models import User
from backend.common.exceptions import ForbiddenError
from backend.common.types import BorrowStatus

POLICY = OverduePolicy(
    grace_days=3, daily_fine=Decimal("1"), cap_ratio=Decimal("0.5"), first_free=True
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_child(db, openid="fp1"):
    user = User(openid=openid, phone="13800000001")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="罚款测试", age=7, grade="二年级", status=1)
    db.add(child)
    db.commit()
    return child


def _mk_book(db, isbn="FP001", price=Decimal("80")):
    book = Book(
        isbn=isbn,
        title="罚款书",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=1000,
        price=price,
    )
    db.add(book)
    db.commit()
    return book


def _mk_borrow(db, child, book, days_past_due, status=BorrowStatus.OVERDUE):
    record = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        status=status,
        borrow_time=datetime.now() - timedelta(days=days_past_due + 21),
        due_date=datetime.now() - timedelta(days=days_past_due),
    )
    db.add(record)
    db.commit()
    return record


class TestCalcOverdueDays:
    def test_due_day_is_zero(self):
        now = datetime.now()
        assert calc_overdue_days(now, now) == 0

    def test_next_day_is_one(self):
        now = datetime.now()
        assert calc_overdue_days(now, now - timedelta(days=1)) == 1

    def test_future_due_is_zero(self):
        now = datetime.now()
        assert calc_overdue_days(now, now + timedelta(days=5)) == 0


class TestCalcFine:
    def test_within_grace_free(self):
        """宽限期 3 天内免罚"""
        assert calc_fine(3, Decimal("80"), POLICY) == Decimal("0")

    def test_day4_charges_one_day(self):
        """第 4 天起算 1 天"""
        assert calc_fine(4, Decimal("80"), POLICY) == Decimal("1.00")

    def test_cap_at_half_price(self):
        """上限 = 定价 × 0.5"""
        # 逾期 100 天 → 97 元，上限 80×0.5=40
        assert calc_fine(100, Decimal("80"), POLICY) == Decimal("40.00")

    def test_no_price_no_cap(self):
        assert calc_fine(10, None, POLICY) == Decimal("7.00")


class TestFirstOverdueFree:
    def test_first_overdue_waived(self, db):
        """首次逾期免罚：fine=0、fine_waived=1、fine_original 留痕"""
        child = _mk_child(db)
        book = _mk_book(db)
        record = _mk_borrow(db, child, book, days_past_due=10)

        apply_fine(db, record, 10, POLICY)
        db.commit()

        assert record.fine_amount == Decimal("0")
        assert record.fine_waived == 1
        assert record.fine_original == Decimal("7.00")  # 10-3 天 × 1 元
        assert record.overdue_days == 10

    def test_second_overdue_charged(self, db):
        """第二次逾期正常计费"""
        child = _mk_child(db)
        book1 = _mk_book(db, "FP002")
        book2 = _mk_book(db, "FP003")
        first = _mk_borrow(db, child, book1, days_past_due=10)
        apply_fine(db, first, 10, POLICY)
        db.commit()

        second = _mk_borrow(db, child, book2, days_past_due=8)
        apply_fine(db, second, 8, POLICY)
        db.commit()

        assert second.fine_waived == 0
        assert second.fine_amount == Decimal("5.00")  # 8-3 天 × 1 元
        assert not is_first_overdue(db, child.id, exclude_id=second.id)

    def test_waived_record_stays_free_on_recalc(self, db):
        """已免罚记录再次累计时保持免罚"""
        child = _mk_child(db)
        book = _mk_book(db)
        record = _mk_borrow(db, child, book, days_past_due=10)
        apply_fine(db, record, 10, POLICY)
        db.commit()

        apply_fine(db, record, 15, POLICY)  # 定时任务再次累计
        assert record.fine_waived == 1
        assert record.fine_amount == Decimal("0")
        assert record.fine_original == Decimal("12.00")  # 15-3

    def test_first_free_disabled_by_config(self, db):
        """配置关闭首次免罚后正常计费（保留修改接口）"""
        policy = OverduePolicy(
            grace_days=3,
            daily_fine=Decimal("1"),
            cap_ratio=Decimal("0.5"),
            first_free=False,
        )
        child = _mk_child(db)
        book = _mk_book(db)
        record = _mk_borrow(db, child, book, days_past_due=6)
        apply_fine(db, record, 6, policy)
        assert record.fine_amount == Decimal("3.00")
        assert record.fine_waived == 0


class TestAudioLockGrace:
    """B8：宽限期 3 天内正常听，第 4 天起锁"""

    def _mk_page(self, db, book):
        page = BookPage(
            book_id=book.id,
            page_number=1,
            content_type=0,
            text_content="p1",
            audio_url="/a.mp3",
        )
        db.add(page)
        db.commit()

    def test_within_grace_not_locked(self, db):
        child = _mk_child(db, "fp_audio1")
        book = _mk_book(db, "FP004")
        self._mk_page(db, book)
        _mk_borrow(db, child, book, days_past_due=2)

        svc = ReadingService(db)
        pages = svc.get_book_pages(book.id, child.id)
        assert len(pages) == 1

    def test_beyond_grace_locked(self, db):
        child = _mk_child(db, "fp_audio2")
        book = _mk_book(db, "FP005")
        self._mk_page(db, book)
        _mk_borrow(db, child, book, days_past_due=5)

        svc = ReadingService(db)
        with pytest.raises(ForbiddenError, match="借阅已逾期"):
            svc.get_book_pages(book.id, child.id)


class TestRefundFreeDays:
    """A4：前 7 天无理由全退，第 8 天起按天扣"""

    def _calc(self, db, amount, order_type, used_days):
        from backend.domain.refund.service import RefundService
        from backend.domain.order.models import Order

        order = Order(
            order_no="FP-REFUND-1",
            user_id=1,
            child_id=1,
            type=order_type,
            amount=Decimal(str(amount)),
            pay_status=1,
        )
        svc = RefundService(db)
        return svc._calculate(order, used_days)

    def test_within_free_days_full_refund(self, db):
        from backend.common.types import OrderType

        assert self._calc(db, 500, OrderType.OBSERVATION, 5) == Decimal("500.00")

    def test_observation_45_days_formula(self, db):
        """A3+A4：500 - 500÷45×(10-7) = 466.67"""
        from backend.common.types import OrderType

        assert self._calc(db, 500, OrderType.OBSERVATION, 10) == Decimal("466.67")

    def test_member_free_days(self, db):
        """5400 - 5400÷365×(30-7) = 5059.73"""
        from backend.common.types import OrderType

        assert self._calc(db, 5400, OrderType.OFFICIAL_MEMBER, 30) == Decimal("5059.73")
