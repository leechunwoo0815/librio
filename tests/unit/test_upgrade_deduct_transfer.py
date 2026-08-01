# tests/unit/test_upgrade_deduct_transfer.py
"""批次7 单元测试 — A6 升级抵扣 + A5 门店收款码/对公转账

- A6：观察期中途购买会员，按剩余天数抵扣观察期剩余价值
  （实付÷45×剩余天数，记录 upgrade_deduct；配置可关）
- A5：对公转账确认到账走标准支付回调链路（pay_type=2，幂等）
- A5：门店收款码为待支付订单生成支付参数
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.config_service import ConfigService
import backend.common.config_audit_model  # noqa: F401
from backend.common.exceptions import ConflictError
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.order.schemas import OrderCreate
from backend.domain.order.service import OrderService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    ConfigService.invalidate()


def _mk_observation_child(db, remaining_days=20, obs_amount=Decimal("500")):
    user = User(openid="ud1", phone="13800000601")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="升级",
        age=7,
        grade="二年级",
        status=MemberStatus.OBSERVATION,
        member_start_time=datetime.now() - timedelta(days=25),
        member_expire_time=datetime.now() + timedelta(days=remaining_days),
    )
    db.add(child)
    db.commit()
    obs_order = Order(
        order_no="UD-OBS-1",
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OBSERVATION,
        amount=obs_amount,
        pay_status=PayStatus.PAID,
        pay_time=datetime.now() - timedelta(days=25),
    )
    db.add(obs_order)
    db.commit()
    return user, child


class TestUpgradeDeduct:
    """A6：500÷45×19（timedelta.days 截断）= 211.11 抵扣，5400 → 5188.89"""

    def test_upgrade_deducts_remaining_value(self, db):
        user, child = _mk_observation_child(db, remaining_days=20)
        svc = OrderService(db)
        result = svc.create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.OFFICIAL_MEMBER)
        )
        assert result.upgrade_deduct == Decimal("211.11")
        assert result.amount == Decimal("5188.89")

    def test_no_deduct_when_disabled(self, db):
        """配置关闭 → 不抵扣（保留修改接口）"""
        ConfigService.set_config(db, "upgrade_deduct_enabled", "false")
        user, child = _mk_observation_child(db)
        svc = OrderService(db)
        result = svc.create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.OFFICIAL_MEMBER)
        )
        assert result.upgrade_deduct == Decimal("0")
        assert result.amount == Decimal("5400.00")

    def test_no_deduct_when_expired(self, db):
        """观察期已结束（EXPIRED 状态）→ 不抵扣"""
        user, child = _mk_observation_child(db, remaining_days=-1)
        child.status = MemberStatus.EXPIRED
        child.member_expire_time = datetime.now() - timedelta(days=1)
        db.commit()
        svc = OrderService(db)
        result = svc.create_order(
            user.id, OrderCreate(child_id=child.id, type=OrderType.OFFICIAL_MEMBER)
        )
        assert result.upgrade_deduct == Decimal("0")


class TestBankTransfer:
    def test_confirm_transfer_marks_paid(self, db):
        user, child = _mk_observation_child(db)
        order = Order(
            order_no="UD-BANK-1",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OFFICIAL_MEMBER,
            amount=Decimal("5400"),
            pay_status=PayStatus.PENDING,
        )
        db.add(order)
        db.commit()

        svc = OrderService(db)
        result = svc.confirm_bank_transfer(
            "UD-BANK-1", trade_no="GS20260801", admin_id=1
        )
        assert result.pay_status == PayStatus.PAID
        assert result.pay_type == 2
        assert result.trade_no == "GS20260801"

    def test_confirm_transfer_idempotent_blocked(self, db):
        """已支付订单不可重复确认"""
        user, child = _mk_observation_child(db)
        order = Order(
            order_no="UD-BANK-2",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OFFICIAL_MEMBER,
            amount=Decimal("5400"),
            pay_status=PayStatus.PAID,
            pay_time=datetime.now(),
        )
        db.add(order)
        db.commit()
        svc = OrderService(db)
        with pytest.raises(ConflictError, match="已支付"):
            svc.confirm_bank_transfer("UD-BANK-2", trade_no="X", admin_id=1)


class TestPayCode:
    def test_pay_code_for_pending_order(self, db):
        user, child = _mk_observation_child(db)
        order = Order(
            order_no="UD-CODE-1",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500"),
            pay_status=PayStatus.PENDING,
        )
        db.add(order)
        db.commit()

        gateway = MagicMock()
        gateway.create_order = AsyncMock(
            return_value=MagicMock(
                success=True, pay_params={"code_url": "weixin://mock"}
            )
        )
        svc = OrderService(db)
        result = asyncio.run(svc.generate_pay_code("UD-CODE-1", gateway))
        assert result["order_no"] == "UD-CODE-1"
        assert result["pay_params"]["code_url"] == "weixin://mock"

    def test_pay_code_rejects_paid_order(self, db):
        user, child = _mk_observation_child(db)
        order = Order(
            order_no="UD-CODE-2",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500"),
            pay_status=PayStatus.PAID,
            pay_time=datetime.now(),
        )
        db.add(order)
        db.commit()
        svc = OrderService(db)
        with pytest.raises(ConflictError, match="不允许支付"):
            asyncio.run(svc.generate_pay_code("UD-CODE-2", MagicMock()))
