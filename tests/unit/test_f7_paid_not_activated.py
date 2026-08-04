# tests/unit/test_f7_paid_not_activated.py
"""F7 回归测试：支付成功但会员未激活 → 订单留痕 + 每日对账任务告警/人工队列

路线（专家裁定）：保留支付、不抛异常回滚；handler warn-skip 时落 activation_issue + OperationLog，
每日对账任务扫描 PAID 未激活订单 → 告警超管 + 自动解除已人工激活的标记。兑现 PRD §1.2"定时修复"。
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.events import OrderPaidEvent
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.order.models import Order
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


def _mk_user_child(db, status=MemberStatus.TRIAL):
    user = User(openid="f7user", phone="13800001001")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F7",
        age=7,
        grade="二年级",
        status=status,
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_paid_order(
    db,
    user,
    child,
    order_type=OrderType.OBSERVATION,
    amount=Decimal("500"),
    order_no="MW-F7-001",
):
    order = Order(
        order_no=order_no,
        user_id=user.id,
        child_id=child.id,
        type=order_type,
        amount=amount,
        pay_status=PayStatus.PAID,
        pay_time=datetime.now() - timedelta(minutes=5),
    )
    db.add(order)
    db.commit()
    return order


class TestHandlerFlagsActivationIssue:
    def test_exited_child_payment_flags_order(self, db):
        """EXITED 孩子支付成功（handler warn-skip）→ order.activation_issue=1 + OperationLog"""
        from backend.domain.admin.models import OperationLog
        from backend.events.order_handlers import handle_order_paid_for_child

        user, child = _mk_user_child(db, status=MemberStatus.EXITED)
        order = _mk_paid_order(db, user, child)
        assert order.activation_issue == 0

        handle_order_paid_for_child(
            OrderPaidEvent(
                order_id=order.id,
                child_id=child.id,
                order_type=OrderType.OBSERVATION,
                amount=Decimal("500"),
            ),
            db,
        )

        db.refresh(order)
        assert order.activation_issue == 1
        oplog = (
            db.query(OperationLog)
            .filter(OperationLog.operation == "paid_not_activated")
            .count()
        )
        assert oplog == 1

    def test_normal_activation_no_flag(self, db):
        """TRIAL 孩子观察期订单支付成功 → 正常激活，不落标记"""
        from backend.events.order_handlers import handle_order_paid_for_child

        user, child = _mk_user_child(db, status=MemberStatus.TRIAL)
        order = _mk_paid_order(db, user, child)

        handle_order_paid_for_child(
            OrderPaidEvent(
                order_id=order.id,
                child_id=child.id,
                order_type=OrderType.OBSERVATION,
                amount=Decimal("500"),
            ),
            db,
        )

        db.refresh(order)
        db.refresh(child)
        assert order.activation_issue == 0
        assert child.status == MemberStatus.OBSERVATION


class TestReconcileTask:
    def _flag_order(self, db, order):
        order.activation_issue = 1
        db.commit()

    def test_alerts_unresolved_order(self, db):
        """未激活订单 → 超管告警，标记保留"""
        from backend.domain.message.models import SystemMessage
        from backend.tasks.scheduler import check_paid_not_activated

        user, child = _mk_user_child(db, status=MemberStatus.TRIAL)
        order = _mk_paid_order(db, user, child)
        self._flag_order(db, order)

        check_paid_not_activated(db)

        alerts = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == 0, SystemMessage.title == "支付未激活告警")
            .count()
        )
        assert alerts == 1
        db.refresh(order)
        assert order.activation_issue == 1

    def test_resolves_when_activated(self, db):
        """孩子已被人工激活（member_expire_time > pay_time）→ 清除标记，不告警"""
        from backend.domain.message.models import SystemMessage
        from backend.tasks.scheduler import check_paid_not_activated

        user, child = _mk_user_child(db, status=MemberStatus.OBSERVATION)
        order = _mk_paid_order(db, user, child)
        child.member_start_time = datetime.now() - timedelta(days=1)
        child.member_expire_time = datetime.now() + timedelta(days=44)
        db.commit()
        self._flag_order(db, order)

        check_paid_not_activated(db)

        db.refresh(order)
        assert order.activation_issue == 0
        alerts = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == 0, SystemMessage.title == "支付未激活告警")
            .count()
        )
        assert alerts == 0

    def test_alert_dedup_within_7_days(self, db):
        """7 天内同单不重复告警"""
        from backend.domain.message.models import SystemMessage
        from backend.tasks.scheduler import check_paid_not_activated

        user, child = _mk_user_child(db, status=MemberStatus.TRIAL)
        order = _mk_paid_order(db, user, child)
        self._flag_order(db, order)

        check_paid_not_activated(db)
        check_paid_not_activated(db)

        alerts = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == 0, SystemMessage.title == "支付未激活告警")
            .count()
        )
        assert alerts == 1
