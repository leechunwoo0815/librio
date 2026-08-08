# tests/unit/test_f053_cancel_order_lock.py
"""F-053 取消订单竞态回归测试

根因：cancel_order 先查后改无行锁——与支付回调并发可把已 PAID 覆盖为 CLOSED
（close_expired_orders 已修，cancel_order 同类漏改）。
并发串行化由 scripts/verify_mysql_concurrency.py 场景 E 实证（RED 30/30 → GREEN 0/30）。
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ValidationError
from backend.common.types import PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.order.models import Order
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


def _mk_order(db, pay_status=PayStatus.PENDING):
    user = User(openid="f053user", phone="13800005301")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="F053", age=7, grade="二年级")
    db.add(child)
    db.commit()
    order = Order(
        order_no=f"ORD-053-{datetime.now().timestamp():.0f}",
        user_id=user.id,
        child_id=child.id,
        type=2,
        amount=Decimal("500"),
        pay_status=pay_status,
        create_time=datetime.now() - timedelta(minutes=1),
    )
    db.add(order)
    db.commit()
    return user.id, order


class TestF053CancelOrder:
    def test_pending_cancel_succeeds(self, db):
        user_id, order = _mk_order(db)
        result = OrderService(db).cancel_order(order.id, user_id)
        assert result.pay_status == PayStatus.CLOSED

    def test_paid_order_cancel_rejected(self, db):
        """已支付订单不可取消——修复前并发窗口会把 PAID 覆盖为 CLOSED"""
        user_id, order = _mk_order(db, pay_status=PayStatus.PAID)
        order.pay_time = datetime.now()
        db.commit()
        svc = OrderService(db)
        with pytest.raises(ValidationError, match="仅可取消未支付"):
            svc.cancel_order(order.id, user_id)
        db.refresh(order)
        assert order.pay_status == PayStatus.PAID

    def test_other_user_cancel_rejected(self, db):
        _, order = _mk_order(db)
        with pytest.raises(ValidationError, match="订单不存在"):
            OrderService(db).cancel_order(order.id, 999)
