# tests/unit/test_batch2_refund_deposit_guards.py
"""批次 2 模式族 A：F-005/006/007/009 状态转移守卫"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.domain.parent_course_time.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.exceptions import ValidationError
from backend.common.types import DepositStatus, PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.deposit.schemas import DepositRefundRequest
from backend.domain.deposit.service import DepositService
from backend.domain.order.models import Order
from backend.domain.order.schemas import OrderPayCallback
from backend.domain.order.service import OrderService
from backend.domain.refund.models import RefundApplication
from backend.domain.refund.service import RefundService
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


def _mk_order(db, pay_status=PayStatus.PAID, refund_status=0, pay_time=None):
    user = User(openid="b2user", phone="13800002001")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="B2", age=7, grade="二年级")
    db.add(child)
    db.commit()
    order = Order(
        order_no="ORD-B2-1",
        user_id=user.id,
        child_id=child.id,
        type=2,
        amount=Decimal("500"),
        pay_status=pay_status,
        refund_status=refund_status,
        pay_time=pay_time or (datetime.now() - timedelta(days=5)),
    )
    db.add(order)
    db.commit()
    return user, order


class TestF005RollbackRefundedGuard:
    def test_rollback_skips_refunded_order(self, db):
        _, order = _mk_order(db, pay_status=PayStatus.REFUNDED, refund_status=2)
        RefundService._rollback_refund_failure(db, 0, order.order_no, "测试")
        db.refresh(order)
        assert order.refund_status == 2  # 保持 REFUNDED
        assert order.pay_status == PayStatus.REFUNDED  # 不被覆盖为 PAID


class TestF006DepositRefundGuard:
    def test_refund_rejects_pending_deposit(self, db):
        user = User(openid="b2dep", phone="13800002002")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="D", age=7, grade="一")
        db.add(child)
        db.commit()
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200"),
            original_amount=Decimal("1200"),
            status=DepositStatus.PENDING,
            pay_order_id="DP-B2-001",
        )
        db.add(rec)
        db.commit()
        svc = DepositService(db)
        with pytest.raises(ValidationError, match="仅已缴纳"):
            svc.refund_deposit(DepositRefundRequest(child_id=child.id))


class TestF007PaidCallbackRefundedGuard:
    def test_callback_ignored_for_refunded_order(self, db):
        _, order = _mk_order(db, pay_status=PayStatus.REFUNDED, refund_status=2)
        svc = OrderService(db)
        result = svc.handle_payment_callback(
            OrderPayCallback(
                order_no=order.order_no,
                trade_no="B2-TXN",
                pay_type=1,
                amount=order.amount,
                trade_state="SUCCESS",
            )
        )
        assert result.pay_status == PayStatus.REFUNDED
        db.refresh(order)
        assert order.pay_status == PayStatus.REFUNDED


class TestF009ZeroAmountRefund:
    def test_apply_refund_rejects_zero_amount(self, db):
        """罚款全额抵扣（final_amount=0）→ 拒绝创建 0 元退款单（F-009）"""
        from backend.domain.refund.schemas import RefundCreate

        user, order = _mk_order(
            db, pay_time=datetime.now() - timedelta(days=400)
        )  # 1 年前支付，45 天观察期已用满
        child = db.query(Child).filter(Child.user_id == user.id).first()
        child.outstanding_fines = Decimal("1000")  # 罚款 ≥ 可退金额 → 抵扣后 0
        db.commit()
        svc = RefundService(db)
        with pytest.raises(ValidationError, match="可退金额为 0"):
            svc.apply_refund(
                order.user_id,
                RefundCreate(order_id=order.id, used_days=0, reason="测试"),
            )
        count = (
            db.query(RefundApplication)
            .filter(RefundApplication.order_id == order.id)
            .count()
        )
        assert count == 0
