"""批次5 F-008 回归：FAILED 订单用户侧可取消（不再永久滞留）"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import OrderType, PayStatus
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


def _mk_failed_order(db):
    user = User(openid="f008", phone="13800000800")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="退", age=7, grade="二年级")
    db.add(child)
    db.commit()
    order = Order(
        order_no="MW-F008-001",
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OBSERVATION,
        amount=Decimal("500"),
        pay_status=PayStatus.FAILED,
    )
    db.add(order)
    db.commit()
    return user, order


def test_failed_order_cancellable_by_owner(db):
    user, order = _mk_failed_order(db)
    result = OrderService(db).cancel_order(order.id, user.id)
    assert result.pay_status == PayStatus.CLOSED


def test_paid_order_still_not_cancellable(db):
    from backend.common.exceptions import ValidationError

    user, order = _mk_failed_order(db)
    order.pay_status = PayStatus.PAID
    db.commit()
    with pytest.raises(ValidationError, match="仅可取消"):
        OrderService(db).cancel_order(order.id, user.id)
