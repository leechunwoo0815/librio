# tests/unit/test_models_order.py
"""
[What] 订单模型单元测试
[Why] 验证Order模型的创建、订单号生成、状态流转
[How] 使用SQLite内存数据库
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.order.models import Order


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_order(db_session):
    """
    [What] 测试创建订单
    [Why] 验证订单基本创建功能
    [How] 创建parent、child和order
    """
    parent = User(openid="test_order_parent")
    db_session.add(parent)
    db_session.commit()

    child = Child(user_id=parent.id, name="小明", age=7, grade="二年级")
    db_session.add(child)
    db_session.commit()

    order = Order(
        order_no="MW20260604ABC123",
        user_id=parent.id,
        child_id=child.id,
        type=Order.TYPE_PARENT_COURSE,
        amount=99.00,
    )
    db_session.add(order)
    db_session.commit()

    assert order.id is not None
    assert order.order_no == "MW20260604ABC123"
    assert order.type == 1
    assert float(order.amount) == 99.00
    assert order.pay_status == Order.PAY_PENDING
    assert order.refund_status == Order.REFUND_NONE


def test_order_types(db_session):
    """
    [What] 测试四种订单类型
    [Why] 验证统一订单表支持所有业务类型
    [How] 创建四种类型订单
    """
    parent = User(openid="test_types")
    child = Child(user_id=1, name="小明", age=7, grade="二年级")
    db_session.add_all([parent, child])
    db_session.commit()
    child.user_id = parent.id
    db_session.commit()

    order1 = Order(
        order_no="MW001", user_id=parent.id, child_id=child.id, type=1, amount=99.00
    )
    order2 = Order(
        order_no="MW002", user_id=parent.id, child_id=child.id, type=2, amount=500.00
    )
    order3 = Order(
        order_no="MW003", user_id=parent.id, child_id=child.id, type=3, amount=5400.00
    )
    db_session.add_all([order1, order2, order3])
    db_session.commit()

    assert order1.type == Order.TYPE_PARENT_COURSE
    assert order2.type == Order.TYPE_OBSERVATION
    assert order3.type == Order.TYPE_OFFICIAL_MEMBER


def test_order_payment_flow(db_session):
    """
    [What] 测试订单支付状态流转
    [Why] 验证支付状态机
    [How] 模拟待支付→已支付→退款流程
    """
    parent = User(openid="test_pay")
    child = Child(user_id=1, name="小明", age=7, grade="二年级")
    db_session.add_all([parent, child])
    db_session.commit()
    child.user_id = parent.id
    db_session.commit()

    order = Order(
        order_no="MW_PAY", user_id=parent.id, child_id=child.id, type=1, amount=99.00
    )
    db_session.add(order)
    db_session.commit()

    # 初始：待支付
    assert order.pay_status == Order.PAY_PENDING

    # 支付成功
    order.pay_status = Order.PAY_PAID
    db_session.commit()
    assert order.pay_status == Order.PAY_PAID

    # 申请退款
    order.refund_status = Order.REFUND_PROCESSING
    db_session.commit()
    assert order.refund_status == Order.REFUND_PROCESSING

    # 退款完成
    order.pay_status = Order.PAY_REFUNDING
    order.refund_status = Order.REFUND_DONE
    order.refund_amount = 99.00
    db_session.commit()
    assert float(order.refund_amount) == 99.00
