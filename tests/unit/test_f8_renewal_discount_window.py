# tests/unit/test_f8_renewal_discount_window.py
"""F8 回归测试：续费 9 折只在缓冲期内（到期未超 member_grace_days 天）

此前折扣条件为 child_status == EXPIRED——而 EXPIRED 要过期超 15 天才触发，
导致缓冲期（到期后 0-15 天，状态仍 OFFICIAL）原价、15 天后永久 9 折，窗口完全错位。
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
from backend.common.types import MemberStatus, OrderType
from backend.database import Base
from backend.domain.child.models import Child
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


def _mk_user_child(db, status=MemberStatus.OFFICIAL):
    user = User(openid="f8user", phone="13800008888")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F8",
        age=7,
        grade="二年级",
        status=status,
    )
    db.add(child)
    db.commit()
    return user, child


def _discount(db, user, child, member_expire_time):
    return OrderService(db)._apply_discount(
        user_id=user.id,
        order_type=OrderType.OFFICIAL_MEMBER,
        amount=Decimal("5400"),
        child_status=child.status,
        child_id=child.id,
        member_expire_time=member_expire_time,
    )


class TestRenewalDiscountWindow:
    def test_in_grace_period_gets_discount(self, db):
        """到期 10 天（缓冲期内，状态仍 OFFICIAL）→ 9 折 4860"""
        user, child = _mk_user_child(db)
        price = _discount(db, user, child, datetime.now() - timedelta(days=10))
        assert price == Decimal("4860.00")

    def test_past_grace_period_no_discount(self, db):
        """过期 20 天（超过缓冲期，状态 EXPIRED）→ 原价 5400"""
        user, child = _mk_user_child(db, status=MemberStatus.EXPIRED)
        price = _discount(db, user, child, datetime.now() - timedelta(days=20))
        assert price == Decimal("5400.00")

    def test_active_member_no_discount(self, db):
        """未到期（3 天后到期）→ 原价 5400"""
        user, child = _mk_user_child(db)
        price = _discount(db, user, child, datetime.now() + timedelta(days=3))
        assert price == Decimal("5400.00")

    def test_grace_boundary_last_day_gets_discount(self, db):
        """到期恰满 15 天（缓冲期最后一天）→ 9 折 4860"""
        user, child = _mk_user_child(db)
        price = _discount(db, user, child, datetime.now() - timedelta(days=15))
        assert price == Decimal("4860.00")

    def test_grace_boundary_day_16_no_discount(self, db):
        """到期 16 天（超出缓冲期）→ 原价 5400"""
        user, child = _mk_user_child(db, status=MemberStatus.EXPIRED)
        price = _discount(db, user, child, datetime.now() - timedelta(days=16))
        assert price == Decimal("5400.00")

    def test_expiry_day_itself_gets_discount(self, db):
        """到期日当天（day 0，已过到期时刻）→ 9 折 4860（缓冲期从到期时刻起算）"""
        user, child = _mk_user_child(db)
        price = _discount(db, user, child, datetime.now() - timedelta(minutes=5))
        assert price == Decimal("4860.00")

    def test_not_yet_expired_same_day_no_discount(self, db):
        """到期日当天但未到到期时刻（今晚才到期）→ 原价 5400（day-0 守卫）"""
        user, child = _mk_user_child(db)
        price = _discount(db, user, child, datetime.now() + timedelta(hours=1))
        assert price == Decimal("5400.00")
