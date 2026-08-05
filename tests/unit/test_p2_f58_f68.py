# tests/unit/test_p2_f58_f68.py
"""P2 批：F58/F59/F60/F64/F67/F68

F58: mark_overdue_books 逐条行锁重取 + 状态守卫（防还书竞态覆盖回 OVERDUE）
F59: 损坏报告幂等——同一借阅未终结报告禁止重复登记
F60: 音频锁定改自然日口径（宽限内不锁，超宽限锁）
F64: borrow_from_reservation 事件链路不自提交（调用方统一提交）
F67: 退款到账核销按 min(抵扣额, 当前 outstanding)，窗口内已线上缴清则差额回补
F68: 押金活跃唯一索引（生成列）防并发双单
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import (
    BookCopyStatus,
    BorrowStatus,
    DepositStatus,
    MemberStatus,
    OrderType,
    PayStatus,
)
from backend.database import Base
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mk_user_child(db, status=MemberStatus.OFFICIAL, deposit=DepositStatus.PAID):
    user = User(openid=f"p2_{id(db)}", phone="13800009101")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="P2",
        age=7,
        grade="二年级",
        status=status,
        deposit_status=deposit,
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_book(db, price=Decimal("100.00")):
    book = Book(
        isbn="978P2000001",
        title="P2 Book",
        author="A",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        price=price,
        total_stock=1,
        available_stock=1,
    )
    db.add(book)
    db.commit()
    copy = BookCopy(
        book_id=book.id, barcode="BC-P2-001", status=BookCopyStatus.AVAILABLE
    )
    db.add(copy)
    db.commit()
    return book, copy


class TestF58OverdueTaskStatusGuard:
    def test_task_skips_already_returned_record(self, db):
        """F58：任务行锁重取发现记录已还（状态守卫）→ 不再覆盖回 OVERDUE"""
        from backend.tasks.scheduler import mark_overdue_books

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        record = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            book_copy_id=copy.id,
            status=BorrowStatus.OVERDUE,
            borrow_time=datetime.now() - timedelta(days=10),
            due_date=datetime.now() - timedelta(days=5),
            overdue_days=2,
            fine_amount=Decimal("2.00"),
            fine_in_outstanding=Decimal("2.00"),
        )
        db.add(record)
        db.commit()
        # 模拟并发还书：任务执行前记录已被还（状态 → RETURNED）
        record.status = BorrowStatus.RETURNED
        record.return_time = datetime.now()
        db.commit()

        mark_overdue_books(db=db)
        db.refresh(record)
        assert record.status == BorrowStatus.RETURNED  # 未被覆盖回 OVERDUE


class TestF59DamageReportIdempotent:
    def test_second_report_rejected_while_active(self, db):
        """F59：存在未终结报告时重复登记被拦截"""
        from backend.common.exceptions import ValidationError
        from backend.domain.admin.services.damage_admin_service import (
            DamageAdminService,
        )

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        record = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            book_copy_id=copy.id,
            status=BorrowStatus.BORROWING,
            borrow_time=datetime.now() - timedelta(days=1),
            due_date=datetime.now() + timedelta(days=20),
        )
        db.add(record)
        db.commit()
        svc = DamageAdminService(db)
        svc.create_report(record.id, damage_level=2, admin_id=1)
        with pytest.raises(ValidationError, match="未终结"):
            svc.create_report(record.id, damage_level=2, admin_id=1)


class TestF60AudioLockNaturalDay:
    def test_within_grace_not_locked(self, db):
        """F60：逾期 2 天（宽限 3 天内）不锁音频"""
        from backend.domain.reading.service import ReadingService

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        db.add(
            BorrowRecord(
                child_id=child.id,
                book_id=book.id,
                book_copy_id=copy.id,
                status=BorrowStatus.OVERDUE,
                borrow_time=datetime.now() - timedelta(days=10),
                due_date=datetime.now() - timedelta(days=2),
            )
        )
        db.commit()
        # 不抛异常即未锁
        ReadingService(db)._check_overdue_audio(child.id)

    def test_beyond_grace_locked(self, db):
        """F60：逾期 5 天（超宽限）锁音频"""
        from backend.common.exceptions import ForbiddenError
        from backend.domain.reading.service import ReadingService

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        db.add(
            BorrowRecord(
                child_id=child.id,
                book_id=book.id,
                book_copy_id=copy.id,
                status=BorrowStatus.OVERDUE,
                borrow_time=datetime.now() - timedelta(days=10),
                due_date=datetime.now() - timedelta(days=5),
            )
        )
        db.commit()
        with pytest.raises(ForbiddenError):
            ReadingService(db)._check_overdue_audio(child.id)


class TestF64NoSelfCommitInHandler:
    def test_borrow_from_reservation_no_self_commit(self, db):
        """F64：borrow_from_reservation 不自提交——调用方统一提交（fulfill 全链路可回滚）"""
        import inspect

        from backend.domain.borrow.service import BorrowService

        source = inspect.getsource(BorrowService.borrow_from_reservation)
        # 方法体内不得出现 self.db.commit()
        assert "self.db.commit()" not in source


class TestF67RefundArrivalDeduct:
    def test_fine_paid_in_window_refunds_difference(self, db):
        """F67：退款窗口内家长已线上缴清罚款 → 到账时差额回补，不罚两遍"""
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        child.outstanding_fines = Decimal("0.00")  # 窗口内已缴清
        db.commit()
        order = Order(
            order_no="MW-P2-067",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500.00"),
            pay_status=PayStatus.PAID,
            pay_time=datetime.now(),
        )
        db.add(order)
        db.commit()
        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id,
            child_id=child.id,
            refund_amount=Decimal("450.00"),  # 申请时已扣 50 罚款
            fine_deducted=Decimal("50.00"),
            used_days=5,
            status=RefundApplication.STATUS_APPROVED,
        )
        db.add(refund)
        order.refund_status = 1
        db.commit()

        RefundService(db).mark_refunded(order.order_no)
        db.refresh(refund)
        assert refund.actual_refund_amount == Decimal("500.00")  # 50 差额回补
        assert child.outstanding_fines == Decimal("0.00")


class TestF68DepositActiveUnique:
    def test_duplicate_active_deposit_rejected_by_db(self, db):
        """F68：同一孩子第二条活跃押金被唯一索引拦截（并发双单 DB 兜底）"""
        import sqlalchemy.exc

        _, child = _mk_user_child(db)
        db.add(
            DepositRecord(
                child_id=child.id,
                amount=Decimal("1200.00"),
                status=DepositStatus.PENDING,
                pay_order_id="DP-P2-001",
            )
        )
        db.commit()
        db.add(
            DepositRecord(
                child_id=child.id,
                amount=Decimal("1200.00"),
                status=DepositStatus.PAID,
                pay_order_id="DP-P2-002",
            )
        )
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db.commit()
