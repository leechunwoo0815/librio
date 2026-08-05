# tests/unit/test_f_group.py
"""批次10 单元测试 — F1 迁移/换绑 / F2 毕业 / F5 复活与多孩资格"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ConflictError, ValidationError
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.admin.services.guardian_service import GuardianService
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
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


def _user(db, openid):
    u = User(openid=openid, phone=f"138{abs(hash(openid)) % 100000000:08d}")
    db.add(u)
    db.commit()
    return u


def _child(db, user, name, status=MemberStatus.TRIAL, age=7):
    c = Child(user_id=user.id, name=name, age=age, grade="二年级", status=status)
    db.add(c)
    db.commit()
    return c


class TestMigrateAccount:
    def test_migrate_moves_children_and_orders(self, db):
        old = _user(db, "old1")
        new = _user(db, "new1")
        child = _child(db, old, "小明")
        order = Order(
            order_no="FG-M1",
            user_id=old.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500"),
            pay_status=PayStatus.PAID,
        )
        db.add(order)
        db.commit()

        svc = GuardianService(db)
        result = svc.migrate_account(old.id, new.id, admin_id=1)
        assert result["moved_children"] == 1
        assert result["moved_orders"] == 1
        db.refresh(child)
        db.refresh(order)
        assert child.user_id == new.id
        assert order.user_id == new.id

    def test_migrate_same_user_rejected(self, db):
        u = _user(db, "same1")
        svc = GuardianService(db)
        with pytest.raises(ValidationError, match="相同"):
            svc.migrate_account(u.id, u.id, admin_id=1)


class TestChangeGuardian:
    def test_change_guardian_requires_confirm(self, db):
        u1 = _user(db, "g1")
        u2 = _user(db, "g2")
        child = _child(db, u1, "小明")
        svc = GuardianService(db)
        with pytest.raises(ValidationError, match="双方确认"):
            svc.change_guardian(child.id, u2.id, confirmed=False, admin_id=1)

    def test_change_guardian_moves_child_and_orders(self, db):
        u1 = _user(db, "g3")
        u2 = _user(db, "g4")
        child = _child(db, u1, "小明")
        order = Order(
            order_no="FG-G1",
            user_id=u1.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500"),
            pay_status=PayStatus.PAID,
        )
        db.add(order)
        db.commit()
        svc = GuardianService(db)
        svc.change_guardian(child.id, u2.id, confirmed=True, admin_id=1)
        db.refresh(child)
        db.refresh(order)
        assert child.user_id == u2.id
        assert order.user_id == u2.id


class TestRevive:
    def test_revive_exited_to_trial(self, db):
        u = _user(db, "r1")
        child = _child(db, u, "小明", status=MemberStatus.EXITED)
        child.member_start_time = datetime.now() - timedelta(days=400)
        child.member_expire_time = datetime.now() - timedelta(days=35)
        db.commit()
        svc = GuardianService(db)
        result = svc.revive_child(child.id, admin_id=1, confirmed=True)
        assert result["status"] == 0
        db.refresh(child)
        assert child.status == MemberStatus.TRIAL
        assert child.member_start_time is None

    def test_revive_rejects_non_exited(self, db):
        u = _user(db, "r2")
        child = _child(db, u, "小明", status=MemberStatus.OFFICIAL)
        svc = GuardianService(db)
        with pytest.raises(ConflictError, match="EXITED"):
            svc.revive_child(child.id, admin_id=1, confirmed=True)

    def test_historical_paid_child_counts_multi_child(self, db):
        """F5：复活后的孩子（历史有已付订单）计入多孩优惠资格"""
        u = _user(db, "r3")
        # 大宝：EXITED 但历史有已付观察期订单
        elder = _child(db, u, "大宝", status=MemberStatus.EXITED)
        order = Order(
            order_no="FG-R1",
            user_id=u.id,
            child_id=elder.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500"),
            pay_status=PayStatus.PAID,
        )
        db.add(order)
        db.commit()
        # 二宝：试读，直接报观察期 → 应享 9 折
        second = _child(db, u, "二宝", status=MemberStatus.TRIAL)
        svc = OrderService(db)
        result = svc.create_order(
            u.id, OrderCreate(child_id=second.id, type=OrderType.OBSERVATION)
        )
        assert result.amount == Decimal("450.00")  # 500 × 0.9


class TestGraduation:
    def test_graduate_15_becomes_alumni(self, db):
        from backend.tasks.scheduler import graduate_children

        u = _user(db, "gr1")
        child = _child(db, u, "大宝", status=MemberStatus.OFFICIAL, age=15)
        graduate_children(db)
        db.refresh(child)
        assert child.status == MemberStatus.ALUMNI
        msg = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == u.id, SystemMessage.title == "毕业快乐")
            .first()
        )
        assert msg is not None

    def test_remind_14_once_a_year(self, db):
        from backend.tasks.scheduler import graduate_children

        u = _user(db, "gr2")
        _child(db, u, "二宝", status=MemberStatus.OFFICIAL, age=14)
        graduate_children(db)
        graduate_children(db)  # 第二次执行不重复提醒
        count = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == u.id, SystemMessage.title == "毕业提醒")
            .count()
        )
        assert count == 1
