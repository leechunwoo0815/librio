import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.borrow.models import BorrowRecord

from backend.domain.order.models import Order
from backend.domain.deposit.service import DepositService
from backend.domain.borrow.service import BorrowService
from backend.domain.order.service import OrderService
from backend.domain.deposit.schemas import (
    DepositPayRequest,
    DepositRefundRequest,
    DepositDeductRequest,
)
from backend.domain.borrow.schemas import ReturnBookRequest
from backend.common.types import BorrowStatus, DepositStatus, PayStatus
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


def _make_child(db):
    user = User(openid="test_sm", phone="13800138999")
    db.add(user)
    db.flush()
    child = Child(
        user_id=user.id,
        name="状态机测试",
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
        deposit_status=DepositStatus.UNPAID,
    )
    db.add(child)
    db.flush()
    return user, child


def _make_book(db):
    book = Book(
        isbn="978SM000001",
        title="状态机书本",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=1000,
        total_stock=5,
        available_stock=5,
    )
    db.add(book)
    db.flush()
    return book


class TestDepositStateMachine:
    def test_cannot_refund_unpaid(self, db):
        _, child = _make_child(db)
        db.commit()

        with pytest.raises(Exception):
            DepositService(db).refund_deposit(DepositRefundRequest(child_id=child.id))

    def _gw(self):
        from backend.common.gateways.payment.mock import MockPaymentGateway

        return MockPaymentGateway()

    @pytest.mark.asyncio
    async def test_cannot_deduct_refunded(self, db):
        user, child = _make_child(db)
        child.deposit_status = DepositStatus.PAID
        db.commit()
        svc = DepositService(db)
        await svc.pay_deposit(DepositPayRequest(child_id=child.id), self._gw(), user)

        svc.refund_deposit(DepositRefundRequest(child_id=child.id))
        await svc.audit_refund(
            child.id, "approve", admin_id=1, payment_gateway=self._gw()
        )
        svc.mark_refunded(child.id)

        with pytest.raises(Exception):
            svc.deduct_deposit(
                DepositDeductRequest(
                    child_id=child.id, amount=Decimal("100"), reason="test"
                )
            )

    @pytest.mark.asyncio
    async def test_cannot_refund_already_refunded(self, db):
        user, child = _make_child(db)
        child.deposit_status = DepositStatus.PAID
        db.commit()
        svc = DepositService(db)
        await svc.pay_deposit(DepositPayRequest(child_id=child.id), self._gw(), user)

        svc.refund_deposit(DepositRefundRequest(child_id=child.id))
        await svc.audit_refund(
            child.id, "approve", admin_id=1, payment_gateway=self._gw()
        )
        svc.mark_refunded(child.id)

        with pytest.raises(Exception):
            svc.refund_deposit(DepositRefundRequest(child_id=child.id))

    @pytest.mark.asyncio
    async def test_cancel_refund_back_to_paid(self, db):
        user, child = _make_child(db)
        child.deposit_status = DepositStatus.PAID
        db.commit()
        svc = DepositService(db)
        await svc.pay_deposit(DepositPayRequest(child_id=child.id), self._gw(), user)

        svc.refund_deposit(DepositRefundRequest(child_id=child.id))
        result = svc.cancel_refund(child.id)
        assert result.status == DepositStatus.PAID

        db.refresh(child)
        assert child.deposit_status == DepositStatus.PAID


class TestBorrowStateMachine:
    def test_cannot_return_unborrowed(self, db):
        _, child = _make_child(db)
        book = _make_book(db)
        child.deposit_status = DepositStatus.PAID
        db.commit()

        br = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            borrow_time=datetime.now(),
            due_date=datetime.now() + timedelta(days=21),
            status=BorrowStatus.RETURNED,
        )
        db.add(br)
        db.commit()

        with pytest.raises(Exception, match="不在借阅中"):
            BorrowService(db).return_book(ReturnBookRequest(borrow_record_id=br.id))

    def test_cannot_return_already_returned(self, db):
        _, child = _make_child(db)
        book = _make_book(db)
        child.deposit_status = DepositStatus.PAID
        db.commit()

        svc = BorrowService(db)
        br = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            borrow_time=datetime.now(),
            due_date=datetime.now() + timedelta(days=21),
            status=BorrowStatus.BORROWING,
        )
        db.add(br)
        db.commit()

        svc.return_book(ReturnBookRequest(borrow_record_id=br.id))
        with pytest.raises(Exception, match="不在借阅中"):
            svc.return_book(ReturnBookRequest(borrow_record_id=br.id))

    def test_overdue_auto_calculates_fine(self, db):
        _, child = _make_child(db)
        book = _make_book(db)
        child.deposit_status = DepositStatus.PAID
        db.commit()

        br = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            borrow_time=datetime.now() - timedelta(days=30),
            due_date=datetime.now() - timedelta(days=10),
            status=BorrowStatus.BORROWING,
        )
        db.add(br)
        db.commit()

        svc = BorrowService(db)
        result = svc.return_book(ReturnBookRequest(borrow_record_id=br.id))
        assert result.status == BorrowStatus.RETURNED
        assert result.overdue_days > 0
        assert result.fine_amount > 0


class TestOrderStateMachine:
    def test_order_cancel_only_pending(self, db):
        user, child = _make_child(db)
        db.commit()

        order = Order(
            order_no="ORD-SM-001",
            user_id=user.id,
            child_id=child.id,
            type=3,
            amount=Decimal("5400"),
            pay_status=PayStatus.PAID,
        )
        db.add(order)
        db.commit()

        svc = OrderService(db)
        with pytest.raises(Exception, match="未支付"):
            svc.cancel_order(order.id, user.id)
