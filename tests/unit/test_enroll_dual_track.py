# tests/unit/test_enroll_dual_track.py
"""A1 双轨制 + A7 漏斗改造单元测试

- 双轨制：未完成亲子课也可直接报观察期（parent_course_required 默认 false）
- 配置 parent_course_required=true 可恢复强制前置（保留修改接口）
- 报名来源标记：亲子课支付 → enroll_source=1；直接观察期 → 2
- 亲子课支付不再直接开通观察期（观察期为 500 元独立产品）
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.config_service import ConfigService
import backend.common.config_audit_model  # noqa: F401 — 注册 config_audit_log 表
from backend.common.events import OrderPaidEvent
from backend.common.exceptions import ValidationError
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.order.schemas import OrderCreate
from backend.domain.order.service import OrderService
from backend.domain.user.models import User
from backend.events.order_handlers import handle_order_paid_for_child


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    ConfigService.invalidate()


@pytest.fixture
def user_child(db):
    user = User(openid="dt1", phone="13800000101")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id, name="双轨", age=7, grade="二年级", status=MemberStatus.TRIAL
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_paid_parent_course(db, user_id, child_id):
    order = Order(
        order_no="DT-PC-1",
        user_id=user_id,
        child_id=child_id,
        type=OrderType.PARENT_COURSE,
        amount=Decimal("99"),
        pay_status=PayStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(order)
    db.commit()
    return order


class TestDualTrackObservation:
    def test_direct_observation_without_parent_course(self, db, user_child):
        """双轨制：无亲子课直接报观察期 → 创建成功"""
        user, child = user_child
        svc = OrderService(db)
        result = svc.create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.OBSERVATION)
        )
        assert result.id is not None
        assert result.type == OrderType.OBSERVATION

    def test_forced_funnel_restorable_via_config(self, db, user_child):
        """配置 parent_course_required=true → 恢复强制前置拦截"""
        user, child = user_child
        ConfigService.set_config(db, "parent_course_required", "true")
        svc = OrderService(db)
        with pytest.raises(ValidationError, match="请先完成亲子课程"):
            svc.create_order(
                user.id, OrderCreate(child_id=child.id, type=OrderType.OBSERVATION)
            )

    def test_with_parent_course_still_allowed(self, db, user_child):
        """完成亲子课的传统路径依然可走"""
        user, child = user_child
        _mk_paid_parent_course(db, user.id, child.id)
        svc = OrderService(db)
        result = svc.create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.OBSERVATION)
        )
        assert result.id is not None


class TestEnrollSource:
    def test_parent_course_payment_marks_source_keeps_trial(self, db, user_child):
        """亲子课支付：标记来源=1，孩子保持 TRIAL（不再直接开通观察期）"""
        user, child = user_child
        event = OrderPaidEvent(
            order_id=1, child_id=child.id, order_type=OrderType.PARENT_COURSE
        )
        handle_order_paid_for_child(event, db)
        db.refresh(child)
        assert child.enroll_source == 1
        assert child.status == MemberStatus.TRIAL
        assert child.member_expire_time is None

    def test_observation_payment_marks_source_1_with_course(self, db, user_child):
        """有亲子课订单 → 观察期支付后来源=1"""
        user, child = user_child
        _mk_paid_parent_course(db, user.id, child.id)
        event = OrderPaidEvent(
            order_id=2, child_id=child.id, order_type=OrderType.OBSERVATION
        )
        handle_order_paid_for_child(event, db)
        db.refresh(child)
        assert child.status == MemberStatus.OBSERVATION
        assert child.enroll_source == 1

    def test_observation_payment_marks_source_2_direct(self, db, user_child):
        """无亲子课订单 → 观察期支付后来源=2"""
        user, child = user_child
        event = OrderPaidEvent(
            order_id=3, child_id=child.id, order_type=OrderType.OBSERVATION
        )
        handle_order_paid_for_child(event, db)
        db.refresh(child)
        assert child.status == MemberStatus.OBSERVATION
        assert child.enroll_source == 2

    def test_source_not_overwritten_once_set(self, db, user_child):
        """已有来源标记不被后续支付覆盖"""
        user, child = user_child
        child.enroll_source = 2
        db.commit()
        _mk_paid_parent_course(db, user.id, child.id)
        event = OrderPaidEvent(
            order_id=4, child_id=child.id, order_type=OrderType.OBSERVATION
        )
        handle_order_paid_for_child(event, db)
        db.refresh(child)
        assert child.enroll_source == 2
