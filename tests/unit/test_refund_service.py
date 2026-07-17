import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.refund.service import RefundService
from backend.domain.refund.schemas import RefundCreate
from backend.common.types import PayStatus, OrderType


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup(db):
    user = User(openid="test_refund_svc", phone="13800138031")
    db.add(user)
    db.flush()
    child = Child(
        user_id=user.id,
        name="退款测试",
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
    )
    db.add(child)
    db.flush()
    order = Order(
        order_no="MW_REFUND_SVC_001",
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OBSERVATION,
        amount=Decimal("500.00"),
        pay_status=PayStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(order)
    db.commit()
    return user, child, order


def test_apply_refund_duplicate_raises_conflict(db):
    user, child, order = _setup(db)
    svc = RefundService(db)
    data = RefundCreate(order_id=order.id, used_days=5, reason="不满意")
    r1 = svc.apply_refund(user.id, data)
    assert r1.id is not None
    assert r1.status == RefundApplication.STATUS_PENDING
    with pytest.raises(Exception, match="正在处理|已有|pending|退款申请已存在|重复"):
        svc.apply_refund(user.id, data)
