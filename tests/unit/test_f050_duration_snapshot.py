"""F-050 回归：会员时长下单时冻结快照（与金额冻结同构）

原缺陷：订单金额下单时冻结，激活时长却回调时实时读配置——配置变更窗口
（尤其迟到支付 CLOSED→PAID）导致"按旧价付款按新配置得时长"。
修复：order.duration_days 快照（观察期/年费读配置、季度/半年固定 90/180），
激活与退款均以快照优先，NULL=存量订单配置兜底。
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.common.config_audit_model  # noqa: F401
from backend.common.config_service import ConfigService
from backend.common.events import OrderPaidEvent
from backend.common.types import MemberStatus, OrderType
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


def _mk_user_child(db, status=MemberStatus.TRIAL):
    user = User(openid="f050", phone="13800005000")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id, name="时长", age=7, grade="二年级", status=status
    )
    db.add(child)
    db.commit()
    return user, child


class TestSnapshotWritten:
    def test_observation_snapshot_45(self, db):
        user, child = _mk_user_child(db)
        order = OrderService(db).create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.OBSERVATION)
        )
        assert order.duration_days == 45

    def test_member_snapshots(self, db):
        user, child = _mk_user_child(db, status=MemberStatus.OBSERVATION)
        svc = OrderService(db)
        assert (
            svc.create_order(
                user.id,
                OrderCreate(child_id=child.id, type=OrderType.OFFICIAL_MEMBER),
            ).duration_days
            == 365
        )
        assert (
            svc.create_order(
                user.id,
                OrderCreate(child_id=child.id, type=OrderType.QUARTERLY),
            ).duration_days
            == 90
        )
        assert (
            svc.create_order(
                user.id,
                OrderCreate(child_id=child.id, type=OrderType.SEMI_ANNUAL),
            ).duration_days
            == 180
        )

    def test_parent_course_no_snapshot(self, db):
        user, child = _mk_user_child(db)
        order = OrderService(db).create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.PARENT_COURSE)
        )
        assert order.duration_days is None

    def test_upgrade_order_snapshots(self, db):
        from backend.common.types import PayStatus

        user, child = _mk_user_child(db, status=MemberStatus.OFFICIAL)
        child.member_expire_time = datetime.now() + timedelta(days=100)
        child.member_start_time = datetime.now()
        # 升级路径：季度(90天) → 半年(180天)。需要一条已支付季度订单作为当前周期
        db.add(
            Order(
                order_no="MW-F050-UPG",
                user_id=user.id,
                child_id=child.id,
                type=OrderType.QUARTERLY,
                amount=Decimal("1350"),
                pay_status=PayStatus.PAID,
                pay_time=datetime.now(),
                duration_days=90,
            )
        )
        db.commit()
        order = OrderService(db).create_upgrade_order(
            user.id, child.id, OrderType.SEMI_ANNUAL
        )
        assert order.duration_days == 180

    def test_offline_order_snapshots(self, db):
        from backend.domain.admin.services.order_service import AdminOrderService

        result = AdminOrderService(db).create_offline_order(
            {
                "phone": "13800005001",
                "parent_name": "线下",
                "child_name": "线下娃",
                "child_age": 7,
                "child_grade": "二年级",
                "order_type": OrderType.OBSERVATION,
                "amount": "500",
                "pay_type": 2,
            }
        )
        order = (
            db.query(Order).filter(Order.order_no == result["order_no"]).one()
        )
        assert order.duration_days == 45


class TestActivationUsesSnapshot:
    def test_config_changed_after_order_still_uses_snapshot(self, db):
        """下单快照 45 → 激活前配置改为 60 → 仍按 45 天激活（金额冻结同构）"""
        user, child = _mk_user_child(db)
        order = OrderService(db).create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.OBSERVATION)
        )
        ConfigService.set_config(db, "observation_days", "60")

        handle_order_paid_for_child(
            OrderPaidEvent(
                order_id=order.id,
                child_id=child.id,
                order_type=OrderType.OBSERVATION,
            ),
            db,
        )
        db.refresh(child)
        assert child.status == MemberStatus.OBSERVATION
        expected = datetime.now() + timedelta(days=45)
        assert abs((child.member_expire_time - expected).total_seconds()) < 5

    def test_legacy_order_without_snapshot_uses_config(self, db):
        """存量订单（duration_days=NULL）→ 配置兜底 60"""
        user, child = _mk_user_child(db)
        legacy = Order(
            order_no="MW-F050-LEGACY",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500"),
            duration_days=None,
        )
        db.add(legacy)
        db.commit()
        ConfigService.set_config(db, "observation_days", "60")

        handle_order_paid_for_child(
            OrderPaidEvent(
                order_id=legacy.id,
                child_id=child.id,
                order_type=OrderType.OBSERVATION,
            ),
            db,
        )
        db.refresh(child)
        expected = datetime.now() + timedelta(days=60)
        assert abs((child.member_expire_time - expected).total_seconds()) < 5


class TestRefundUsesSnapshot:
    def test_refund_total_days_from_snapshot(self, db):
        """快照 45：退款按 45 天算；配置改为 60 不影响已下单订单"""
        from backend.common.types import PayStatus

        user, child = _mk_user_child(db)
        created = OrderService(db).create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.OBSERVATION)
        )
        order = db.query(Order).filter(Order.id == created.id).one()
        order.pay_status = PayStatus.PAID
        db.commit()
        ConfigService.set_config(db, "observation_days", "60")

        preview = OrderService(db).calculate_refund(order.id, used_days=5)
        assert preview["total_days"] == 45
