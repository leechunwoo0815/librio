# tests/unit/test_deposit_service.py
"""押金域单元测试"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.borrow.models import BorrowRecord
from backend.domain.deposit.service import DepositService
from backend.domain.deposit.schemas import (
    DepositPayRequest,
    DepositRefundRequest,
    DepositDeductRequest,
    DepositPayResponse,
)
from backend.common.types import BorrowStatus, DepositStatus
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


def _mock_gateway():
    gw = MagicMock()
    gw.create_order = AsyncMock(
        return_value=MagicMock(
            success=True, pay_params={"prepay_id": "mock_prepay_123"}
        )
    )
    gw.supports_instant_payment = True
    return gw


def _setup(db):
    user = User(openid="test_deposit", phone="13800138030")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="押金测试",
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
        deposit_status=DepositStatus.UNPAID,
    )
    db.add(child)
    db.commit()
    return user, child


@pytest.mark.asyncio
async def test_pay_deposit(db):
    user, child = _setup(db)
    svc = DepositService(db)
    result = await svc.pay_deposit(
        DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
    )
    assert result.deposit.status == DepositStatus.PAID
    db.refresh(child)
    assert child.deposit_status == DepositStatus.PAID


@pytest.mark.asyncio
async def test_pay_deposit_duplicate(db):
    user, child = _setup(db)
    svc = DepositService(db)
    await svc.pay_deposit(
        DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
    )
    with pytest.raises(Exception, match="已缴纳"):
        await svc.pay_deposit(
            DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
        )


@pytest.mark.asyncio
async def test_pay_deposit_returns_pay_params(db):
    user, child = _setup(db)
    svc = DepositService(db)
    result = await svc.pay_deposit(
        DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
    )
    assert isinstance(result, DepositPayResponse)
    assert isinstance(result.pay_params, dict)
    assert len(result.pay_params) > 0


@pytest.mark.asyncio
async def test_refund_deposit_success(db):
    user, child = _setup(db)
    svc = DepositService(db)
    await svc.pay_deposit(
        DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
    )
    result = svc.refund_deposit(DepositRefundRequest(child_id=child.id))
    assert result.status == DepositStatus.REFUND_PENDING
    db.refresh(child)
    assert child.deposit_status == DepositStatus.REFUND_PENDING


@pytest.mark.asyncio
async def test_refund_deposit_with_active_borrows(db):
    user, child = _setup(db)
    book = Book(
        isbn="978001",
        title="Test",
        author="A",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        word_count=1000,
    )
    db.add(book)
    db.commit()
    svc = DepositService(db)
    await svc.pay_deposit(
        DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
    )
    borrow = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        status=BorrowStatus.BORROWING,
        borrow_time=datetime.now(),
        due_date=datetime.now(),
    )
    db.add(borrow)
    db.commit()
    with pytest.raises(Exception, match="归还"):
        svc.refund_deposit(DepositRefundRequest(child_id=child.id))


@pytest.mark.asyncio
async def test_refund_deposit_with_fines(db):
    user, child = _setup(db)
    svc = DepositService(db)
    await svc.pay_deposit(
        DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
    )
    child.outstanding_fines = 50
    db.commit()
    with pytest.raises(Exception, match="罚款"):
        svc.refund_deposit(DepositRefundRequest(child_id=child.id))


@pytest.mark.asyncio
async def test_deduct_deposit(db):
    user, child = _setup(db)
    svc = DepositService(db)
    await svc.pay_deposit(
        DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
    )
    result = svc.deduct_deposit(
        DepositDeductRequest(child_id=child.id, amount=Decimal("120"), reason="丢书")
    )
    assert result.status == DepositStatus.DEDUCTED
    db.refresh(child)
    assert child.deposit_status == DepositStatus.DEDUCTED
    assert float(child.outstanding_fines) == 120.0


@pytest.mark.asyncio
async def test_deduct_deposit_exceeds_balance(db):
    user, child = _setup(db)
    svc = DepositService(db)
    await svc.pay_deposit(
        DepositPayRequest(child_id=child.id), _mock_gateway(), current_user=user
    )
    with pytest.raises(Exception, match="超过"):
        svc.deduct_deposit(
            DepositDeductRequest(
                child_id=child.id, amount=Decimal("2000"), reason="巨额"
            )
        )
