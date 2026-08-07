# tests/unit/test_f15_f16_f23.py
"""F15/F16/F23 回归测试 — P3 可推进批（20260807）

- F15：tiers 文案动态取 observation_days 配置（禁硬编码 30 天）
- F16：升级/抵扣单支付后会员期重置起算（禁止"抵扣+叠加"双重受益）；
  升级差额剩余价值按当前周期订单实付金额计算
- F23：14 岁毕业提醒独立留痕（grad_remind_year 自然年去重，不依赖消息保留期）
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
from backend.common.config_service import ConfigService
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.order.models import Order
from backend.domain.order.schemas import OrderCreate, OrderPayCallback
from backend.domain.order.service import OrderService
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
    ConfigService.invalidate()


def _user(db, openid="f1523user", phone="13800002001"):
    u = User(openid=openid, phone=phone)
    db.add(u)
    db.commit()
    return u


def _child(
    db,
    user,
    name="小宝",
    status=MemberStatus.TRIAL,
    age=7,
    expire=None,
    start=None,
):
    c = Child(
        user_id=user.id,
        name=name,
        age=age,
        grade="二年级",
        status=status,
        member_start_time=start,
        member_expire_time=expire,
    )
    db.add(c)
    db.commit()
    return c


class TestF15TiersDynamic:
    def test_tiers_unit_and_report_desc_from_config(self, db):
        from backend.domain.order.router import get_product_tiers

        resp = get_product_tiers(order_service=OrderService(db))
        obs = next(t for t in resp.tiers if t.type == 2)
        assert obs.unit == "45天"
        assert any("45天后生成" in f.desc for f in obs.features)
        assert "30天" not in obs.unit

    def test_tiers_follow_config_change(self, db):
        ConfigService.set_config(db, "observation_days", "60")
        from backend.domain.order.router import get_product_tiers

        resp = get_product_tiers(order_service=OrderService(db))
        obs = next(t for t in resp.tiers if t.type == 2)
        assert obs.unit == "60天"
        assert any("60天后生成" in f.desc for f in obs.features)


class TestF16UpgradeReset:
    def test_upgrade_order_resets_expiry(self, db):
        """观察期中途升级（A6 抵扣）：支付后会员期重置为 now+365，不叠加剩余观察期"""
        u = _user(db)
        obs_start = datetime.now() - timedelta(days=25)
        obs_end = datetime.now() + timedelta(days=20)
        child = _child(
            db,
            u,
            status=MemberStatus.OBSERVATION,
            expire=obs_end,
            start=obs_start,
        )
        # A6 抵扣需要一笔已付观察期订单（实付 500）
        obs_order = Order(
            order_no="F16-OBS",
            user_id=u.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500"),
            pay_status=PayStatus.PAID,
            pay_time=obs_start,
        )
        db.add(obs_order)
        db.commit()
        svc = OrderService(db)
        order = svc.create_order(
            u.id, OrderCreate(child_id=child.id, type=OrderType.OFFICIAL_MEMBER)
        )
        assert order.upgrade_deduct > 0  # 观察期剩余价值已抵扣

        svc.handle_payment_callback(
            OrderPayCallback(
                order_no=order.order_no,
                trade_no="F16-TXN-UPG",
                pay_type=1,
                amount=order.amount,
                trade_state="SUCCESS",
            )
        )
        db.refresh(child)
        assert child.status == MemberStatus.OFFICIAL
        expected = datetime.now() + timedelta(days=365)
        assert abs((child.member_expire_time - expected).total_seconds()) < 60
        # 会员期重置起算（不再是观察期开始时间）
        assert abs((child.member_start_time - datetime.now()).total_seconds()) < 60

    def test_renewal_extends_existing_expiry(self, db):
        """普通续费（无抵扣）仍叠加：现有到期时间 + 365"""
        u = _user(db, openid="f16renew")
        now = datetime.now()
        expire = now + timedelta(days=50)
        child = _child(
            db,
            u,
            status=MemberStatus.OFFICIAL,
            expire=expire,
            start=now - timedelta(days=315),
        )
        order = Order(
            order_no="F16-RENEW",
            user_id=u.id,
            child_id=child.id,
            type=OrderType.OFFICIAL_MEMBER,
            amount=Decimal("5400"),
            pay_status=PayStatus.PENDING,
        )
        db.add(order)
        db.commit()

        svc = OrderService(db)
        svc.handle_payment_callback(
            OrderPayCallback(
                order_no=order.order_no,
                trade_no="F16-TXN-RENEW",
                pay_type=1,
                amount=order.amount,
                trade_state="SUCCESS",
            )
        )
        db.refresh(child)
        expected = expire + timedelta(days=365)
        assert abs((child.member_expire_time - expected).total_seconds()) < 60

    def test_upgrade_remaining_value_uses_paid_amount(self, db):
        """升级差额剩余价值按当前订单实付（9 折续费 1215）而非现价 1350 计算"""
        u = _user(db, openid="f16paid")
        now = datetime.now()
        child = _child(
            db,
            u,
            status=MemberStatus.EXPIRED,
            expire=now - timedelta(days=3),
            start=now - timedelta(days=362),
        )
        svc = OrderService(db)
        # 真实续费路径：缓冲期内续季度 → 9 折实付 1215
        order = svc.create_order(
            u.id, OrderCreate(child_id=child.id, type=OrderType.QUARTERLY)
        )
        assert order.amount == Decimal("1215.00")
        svc.handle_payment_callback(
            OrderPayCallback(
                order_no=order.order_no,
                trade_no="F16-TXN-PAID",
                pay_type=1,
                amount=order.amount,
                trade_state="SUCCESS",
            )
        )
        db.refresh(child)
        assert child.status == MemberStatus.OFFICIAL

        options = svc.get_upgrade_options(child.id)
        assert options
        # 剩余价值 = 实付 1215 × 剩余天数/90（非现价 1350）；
        # remaining_days 有 timedelta.days 截断，期望值按截断口径动态计算
        db.refresh(child)
        remaining_days = max(0, (child.member_expire_time - datetime.now()).days)
        expected_value = (
            Decimal("1215.00") * Decimal(str(remaining_days)) / Decimal("90")
        ).quantize(Decimal("0.01"))
        assert Decimal(options[0]["remaining_value"]) == expected_value
        # 现价口径会被多孩/续费折扣后高估，这里显式验证用的是实付 1215
        assert Decimal(options[0]["remaining_value"]) != Decimal("1350.00")
        expected_upgrade = (Decimal("2700.00") - expected_value).quantize(
            Decimal("0.01")
        )
        assert Decimal(options[0]["upgrade_price"]) == expected_upgrade


class TestF23GradReminderDedup:
    def test_no_remind_after_message_purged_same_year(self, db):
        """F23：purge 物理删除提醒消息后，同年不再重复提醒（独立留痕字段兜底）"""
        from backend.tasks.scheduler import graduate_children

        u = _user(db, openid="f23purge")
        child = _child(db, u, status=MemberStatus.OFFICIAL, age=14)
        graduate_children(db)
        graduate_children(db)  # 同年第二次执行不重复
        assert (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == u.id, SystemMessage.title == "毕业提醒")
            .count()
            == 1
        )
        db.refresh(child)
        assert child.grad_remind_year == datetime.now().year

        # 模拟 purge：物理删除全部提醒消息后再执行任务
        db.query(SystemMessage).filter(SystemMessage.title == "毕业提醒").delete()
        db.commit()
        graduate_children(db)
        assert (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == u.id, SystemMessage.title == "毕业提醒")
            .count()
            == 0
        )
        db.refresh(child)
        assert child.grad_remind_year == datetime.now().year

    def test_reminds_again_in_new_year(self, db):
        from backend.tasks.scheduler import graduate_children

        u = _user(db, openid="f23newyr")
        child = _child(db, u, status=MemberStatus.OFFICIAL, age=14)
        child.grad_remind_year = datetime.now().year - 1
        db.commit()
        graduate_children(db)
        assert (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == u.id, SystemMessage.title == "毕业提醒")
            .count()
            == 1
        )
        db.refresh(child)
        assert child.grad_remind_year == datetime.now().year
