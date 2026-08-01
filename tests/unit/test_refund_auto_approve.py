# tests/unit/test_refund_auto_approve.py
"""批次3 审核自动化单元测试 — E1/E7/B11/A2

- E1a：退款 ≤ refund_auto_approve_max（默认500）自动审核通过
- E7：未缴罚款从退款中自动抵扣（fine_deducted 留痕，完成时核销）
- B11：押金退款自动抵扣未缴罚款（不再拦截）
- A2：借满 10 本无逾期 → 押金减半退还 600（一次为限）
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import (
    BorrowStatus,
    DepositStatus,
    OrderType,
    PayStatus,
)
from backend.database import Base
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.deposit.schemas import DepositRefundRequest
from backend.domain.deposit.service import DepositService
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.refund.schemas import RefundCreate
from backend.domain.refund.service import RefundService
from backend.domain.user.models import User
from backend.common.exceptions import ConflictError, ValidationError


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_user_child(db, openid="ra1"):
    user = User(openid=openid, phone="13800000201")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="退款测试",
        age=7,
        grade="二年级",
        status=Child.STATUS_OBSERVATION,
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_paid_order(
    db, user, child, amount, order_type=OrderType.OBSERVATION, days_ago=10
):
    order = Order(
        order_no=f"RA-{order_type}-{amount}-{days_ago}",
        user_id=user.id,
        child_id=child.id,
        type=order_type,
        amount=Decimal(str(amount)),
        pay_status=PayStatus.PAID,
        pay_time=datetime.now() - timedelta(days=days_ago),
    )
    db.add(order)
    db.commit()
    return order


def _mk_paid_deposit(db, child, amount=Decimal("1200")):
    record = DepositRecord(
        child_id=child.id,
        amount=amount,
        status=DepositStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(record)
    child.deposit_status = DepositStatus.PAID
    db.commit()
    return record


class TestRefundAutoApprove:
    """E1a：≤500 自动通过；>500 保持人工"""

    def test_small_refund_auto_approved(self, db):
        user, child = _mk_user_child(db)
        # 观察期用 10 天：500 - 500÷45×3 = 466.67 ≤ 500
        order = _mk_paid_order(db, user, child, 500)
        svc = RefundService(db)
        result = svc.apply_refund(
            user.id, RefundCreate(order_id=order.id, used_days=10, reason="测试")
        )
        assert result.status == RefundApplication.STATUS_APPROVED
        assert result.refund_amount == Decimal("466.67")
        db.refresh(order)
        assert order.refund_status == 1

    def test_large_refund_stays_pending(self, db):
        user, child = _mk_user_child(db)
        # 正式会员用 30 天：5059.73 > 500
        order = _mk_paid_order(
            db, user, child, 5400, OrderType.OFFICIAL_MEMBER, days_ago=30
        )
        svc = RefundService(db)
        result = svc.apply_refund(
            user.id, RefundCreate(order_id=order.id, used_days=30, reason="测试")
        )
        assert result.status == RefundApplication.STATUS_PENDING


class TestRefundFineDeduction:
    """E7：未缴罚款从退款抵扣，完成时核销"""

    def test_fine_deducted_from_refund(self, db):
        user, child = _mk_user_child(db)
        child.outstanding_fines = Decimal("100")
        db.commit()
        order = _mk_paid_order(
            db, user, child, 5400, OrderType.OFFICIAL_MEMBER, days_ago=30
        )
        svc = RefundService(db)
        result = svc.apply_refund(
            user.id, RefundCreate(order_id=order.id, used_days=30, reason="测试")
        )
        assert result.refund_amount == Decimal("4959.73")  # 5059.73 - 100
        assert result.fine_deducted == Decimal("100")

    def test_fine_cleared_on_mark_refunded(self, db):
        user, child = _mk_user_child(db)
        child.outstanding_fines = Decimal("100")
        db.commit()
        order = _mk_paid_order(db, user, child, 500)
        svc = RefundService(db)
        svc.apply_refund(
            user.id, RefundCreate(order_id=order.id, used_days=10, reason="测试")
        )
        # ≤500 自动通过（466.67 - 100 = 366.67），模拟回调完成
        svc.mark_refunded(order.order_no)
        db.refresh(child)
        assert child.outstanding_fines == Decimal("0")


class TestDepositRefundDeduction:
    """B11：押金退款自动抵扣未缴罚款；E1b：审核尊重预设退款额"""

    def test_refund_deducts_outstanding_fines(self, db):
        user, child = _mk_user_child(db)
        _mk_paid_deposit(db, child)
        child.outstanding_fines = Decimal("50")
        db.commit()
        svc = DepositService(db)
        result = svc.refund_deposit(DepositRefundRequest(child_id=child.id))
        assert result.status == DepositStatus.REFUND_PENDING
        assert result.refund_amount == Decimal("1150")

    def test_fines_cleared_on_mark_refunded(self, db):
        user, child = _mk_user_child(db)
        _mk_paid_deposit(db, child)
        child.outstanding_fines = Decimal("50")
        db.commit()
        svc = DepositService(db)
        svc.refund_deposit(DepositRefundRequest(child_id=child.id))
        # 审核通过（无网关）→ REFUNDING
        import asyncio

        asyncio.run(
            svc.audit_refund(child.id, "approve", admin_id=1, payment_gateway=None)
        )
        svc.mark_refunded(child.id)
        db.refresh(child)
        assert child.outstanding_fines == Decimal("0")
        assert child.deposit_status == DepositStatus.REFUNDED


class TestPartialRefund:
    """A2：借满 10 本无逾期 → 减半退还 600"""

    def _mk_returned_borrows(self, db, child, n, overdue=0):
        for i in range(n):
            r = BorrowRecord(
                child_id=child.id,
                book_id=1000 + i,
                borrow_time=datetime.now() - timedelta(days=30),
                due_date=datetime.now() - timedelta(days=9),
                return_time=datetime.now() - timedelta(days=8),
                status=BorrowStatus.RETURNED,
                overdue_days=overdue,
            )
            db.add(r)
        db.commit()

    def test_partial_refund_success(self, db):
        user, child = _mk_user_child(db)
        _mk_paid_deposit(db, child)
        self._mk_returned_borrows(db, child, 10)
        svc = DepositService(db)
        gw = MagicMock()
        gw.refund = AsyncMock(return_value=MagicMock(success=True))

        import asyncio

        result = asyncio.run(svc.partial_refund_deposit(child.id, gw))
        assert result.amount == Decimal("600")
        assert result.partial_refunded == 1

    def test_partial_refund_needs_10_books(self, db):
        user, child = _mk_user_child(db)
        _mk_paid_deposit(db, child)
        self._mk_returned_borrows(db, child, 9)
        svc = DepositService(db)
        import asyncio

        with pytest.raises(ValidationError, match="借满 10 本"):
            asyncio.run(svc.partial_refund_deposit(child.id, None))

    def test_partial_refund_blocked_by_overdue_history(self, db):
        user, child = _mk_user_child(db)
        _mk_paid_deposit(db, child)
        self._mk_returned_borrows(db, child, 10, overdue=2)
        svc = DepositService(db)
        import asyncio

        with pytest.raises(ValidationError, match="逾期记录"):
            asyncio.run(svc.partial_refund_deposit(child.id, None))

    def test_partial_refund_only_once(self, db):
        user, child = _mk_user_child(db)
        _mk_paid_deposit(db, child)
        self._mk_returned_borrows(db, child, 10)
        svc = DepositService(db)
        import asyncio

        asyncio.run(svc.partial_refund_deposit(child.id, None))
        with pytest.raises(ConflictError, match="限一次"):
            asyncio.run(svc.partial_refund_deposit(child.id, None))
