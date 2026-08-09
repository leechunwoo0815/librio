"""
F-016 终审同类漏改闭环：退款回退/回调路径必须忽略已软删记录。

场景：订单或退款申请被软删后，_rollback_refund_failure / mark_refunded /
handle_refund_failed 不得再修改其状态（避免复活已删除数据或误置位）。
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.refund.service import RefundService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_user_child(db):
    user = User(openid="f016", phone="13800000160")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F016",
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_order(db, user, child, order_no="F016-001"):
    order = Order(
        order_no=order_no,
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OBSERVATION,
        amount=Decimal("500.00"),
        pay_status=PayStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(order)
    db.commit()
    return order


def _mk_refund(db, order, status=RefundApplication.STATUS_APPROVED, deleted=0):
    refund = RefundApplication(
        order_id=order.id,
        user_id=order.user_id,
        child_id=order.child_id,
        refund_amount=Decimal("466.67"),
        status=status,
        is_deleted=deleted,
    )
    db.add(refund)
    db.commit()
    return refund


class TestF016RollbackIgnoresDeleted:
    def test_rollback_ignores_deleted_order(self, db):
        user, child = _mk_user_child(db)
        order = _mk_order(db, user, child)
        order.is_deleted = 1
        refund = _mk_refund(db, order)
        db.commit()

        RefundService._rollback_refund_failure(db, refund.id, order.order_no, "err")

        db.expire_all()
        order = db.query(Order).filter(Order.id == order.id).first()
        refund = db.query(RefundApplication).filter(RefundApplication.id == refund.id).first()
        assert order.refund_status == 0  # 未被置 FAILED
        assert refund.status == RefundApplication.STATUS_APPROVED  # 未被回退

    def test_rollback_ignores_deleted_refund(self, db):
        user, child = _mk_user_child(db)
        order = _mk_order(db, user, child)
        _mk_refund(db, order, deleted=1)

        refund = (
            db.query(RefundApplication)
            .filter(RefundApplication.order_id == order.id)
            .first()
        )
        RefundService._rollback_refund_failure(db, refund.id, order.order_no, "err")

        db.expire_all()
        order = db.query(Order).filter(Order.id == order.id).first()
        refund = db.query(RefundApplication).filter(RefundApplication.id == refund.id).first()
        assert order.refund_status == 3  # 订单未删除，正常置 FAILED
        assert refund.status == RefundApplication.STATUS_APPROVED


class TestF016CallbackIgnoresDeletedRefund:
    def test_mark_refunded_ignores_deleted_refund(self, db):
        user, child = _mk_user_child(db)
        order = _mk_order(db, user, child)
        _mk_refund(db, order, deleted=1)

        svc = RefundService(db)
        with pytest.raises(Exception, match="无待完成的退款申请"):
            svc.mark_refunded(order.order_no)

        db.expire_all()
        order = db.query(Order).filter(Order.id == order.id).first()
        assert order.refund_status == 0

    def test_handle_refund_failed_ignores_deleted_refund(self, db):
        user, child = _mk_user_child(db)
        order = _mk_order(db, user, child)
        _mk_refund(db, order, deleted=1)
        order.refund_status = 1  # 退款中
        db.commit()

        svc = RefundService(db)
        svc.handle_refund_failed(order.order_no, "CLOSED")

        db.expire_all()
        order = db.query(Order).filter(Order.id == order.id).first()
        refund = (
            db.query(RefundApplication)
            .filter(RefundApplication.order_id == order.id)
            .first()
        )
        # 订单仍标记 FAILED（订单未删除，属正常回调处理）；已删除退款单不得回 PENDING
        assert order.refund_status == 3
        assert refund.status == RefundApplication.STATUS_APPROVED
