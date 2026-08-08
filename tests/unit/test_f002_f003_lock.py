# tests/unit/test_f002_f003_lock.py
"""F-002/F-003 行锁回归测试

F-002：_rollback_refund_failure 写 order.refund_status 加行锁（与主流程/回调并发防覆盖）
F-003：_mark_paid_member_ever 写 user.paid_member_ever 加行锁（并发双订单防双写）
并发串行化与 D/E/F 场景同模式（verify_mysql_concurrency.py），本项验证行为不变。
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.domain.parent_course_time.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
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


def _mk_paid_order(db):
    user = User(openid="f002user", phone="13800000201")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="F002", age=7, grade="二年级")
    db.add(child)
    db.commit()
    order = Order(
        order_no="ORD-F002-1",
        user_id=user.id,
        child_id=child.id,
        type=2,
        amount=Decimal("500"),
        pay_status=PayStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(order)
    db.commit()
    return user, order


class TestF002RollbackLock:
    def test_rollback_marks_failed_and_pending(self, db):
        _, order = _mk_paid_order(db)
        refund = RefundApplication(
            order_id=order.id,
            user_id=order.user_id,
            child_id=order.child_id,
            amount=order.amount,
            refund_amount=order.amount,
            status=RefundApplication.STATUS_APPROVED,
        )
        db.add(refund)
        db.commit()

        RefundService._rollback_refund_failure(
            db, refund.id, order.order_no, "测试失败"
        )
        db.refresh(order)
        db.refresh(refund)
        assert order.refund_status == 3  # FAILED
        assert order.pay_status == PayStatus.PAID
        assert refund.status == RefundApplication.STATUS_PENDING
        msg = (
            db.query(SystemMessage)
            .filter(SystemMessage.title == "退款执行失败")
            .first()
        )
        assert msg is not None


class TestF003PaidEverLock:
    def test_payment_callback_sets_paid_member_ever(self, db):
        user = User(openid="f003user", phone="13800000301")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="F003", age=7, grade="二年级")
        db.add(child)
        db.commit()
        order = Order(
            order_no="ORD-F003-1",
            user_id=user.id,
            child_id=child.id,
            type=2,
            amount=Decimal("500"),
            pay_status=PayStatus.PENDING,
        )
        db.add(order)
        db.commit()
        svc = OrderService(db)
        svc.handle_payment_callback(
            OrderPayCallback(
                order_no=order.order_no,
                trade_no="F003-TXN-1",
                pay_type=1,
                amount=order.amount,
                trade_state="SUCCESS",
            )
        )
        db.refresh(user)
        assert user.paid_member_ever == 1
