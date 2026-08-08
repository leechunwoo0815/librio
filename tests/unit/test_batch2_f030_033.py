# tests/unit/test_batch2_f030_033.py
"""批次 2：F-030 网关失败保留回调窗口 / F-031 乱序回调守卫 / F-033 分位四舍五入"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import PaymentError
from backend.common.types import DepositStatus, PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.deposit.schemas import DepositPayRequest
from backend.domain.deposit.service import DepositService
from backend.domain.order.models import Order
from backend.domain.refund.service import RefundService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_user_child(db):
    user = User(openid="b2u", phone="13800002003")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="B2", age=7, grade="二年级")
    db.add(child)
    db.commit()
    return user, child


class TestF030GatewayFailureKeepsPending:
    def test_pay_deposit_gateway_error_keeps_pending(self, db):
        """prepay 抛异常 → 记录保持 PENDING（保留回调窗口，F78 负责超时复位）"""
        user, child = _mk_user_child(db)
        gateway = MagicMock()
        gateway.create_order = AsyncMock(side_effect=RuntimeError("网络超时"))
        svc = DepositService(db)
        with pytest.raises(PaymentError):
            asyncio.run(
                svc.pay_deposit(
                    DepositPayRequest(child_id=child.id),
                    gateway,
                    current_user=user,
                )
            )
        record = (
            db.query(DepositRecord).filter(DepositRecord.child_id == child.id).first()
        )
        assert record.status == DepositStatus.PENDING


class TestF031RefundFailedGuard:
    def test_handle_refund_failed_ignores_refunded(self, db):
        _, child = _mk_user_child(db)
        user = db.query(User).filter(User.id == child.user_id).first()
        order = Order(
            order_no="ORD-B2-F31",
            user_id=user.id,
            child_id=child.id,
            type=2,
            amount=Decimal("500"),
            pay_status=PayStatus.REFUNDED,
            refund_status=2,
            pay_time=datetime.now() - timedelta(days=5),
        )
        db.add(order)
        db.commit()
        RefundService(db).handle_refund_failed(order.order_no, "CLOSED")
        db.refresh(order)
        assert order.refund_status == 2  # 保持 REFUNDED
        assert order.pay_status == PayStatus.REFUNDED  # 不被覆盖为 PAID


class TestF033YuanToCentsRounding:
    def test_yuan_to_cents_rounds_half_up(self):
        from backend.common.gateways.payment.types import yuan_to_cents

        assert yuan_to_cents(Decimal("0.005")) == 1  # 四舍五入（原 int 截断为 0）
        assert yuan_to_cents(Decimal("0.004")) == 0
        assert yuan_to_cents(Decimal("1200.00")) == 120000
