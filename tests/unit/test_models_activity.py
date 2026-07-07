# tests/unit/test_models_activity.py
"""
[What] 活动和退款模型单元测试
[Why] 验证Activity、ActivityEnrollment、RefundApplication模型
[How] 使用SQLite内存数据库
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.activity.models import Activity, ActivityEnrollment
from backend.domain.refund.models import RefundApplication


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_activity(db_session):
    """
    [What] 测试创建活动
    [Why] 验证活动基本字段
    [How] 创建免费和收费活动
    """
    now = datetime.now()
    free = Activity(
        title="读书交流会",
        type=Activity.TYPE_READING,
        max_participants=30,
        start_time=now + timedelta(days=7),
        end_time=now + timedelta(days=7, hours=2),
        venue_id=1,
    )
    db_session.add(free)
    db_session.commit()

    assert free.id is not None
    assert free.type == Activity.TYPE_READING
    assert free.current_participants == 0

    paid = Activity(
        title="专家讲座",
        type=Activity.TYPE_LECTURE,
        price=100.00,
        max_participants=50,
        start_time=now + timedelta(days=14),
        end_time=now + timedelta(days=14, hours=2),
        venue_id=1,
    )
    db_session.add(paid)
    db_session.commit()

    assert paid.type == Activity.TYPE_LECTURE
    assert float(paid.price) == 100.00


def test_activity_enrollment(db_session):
    """
    [What] 测试活动报名
    [Why] 验证报名记录和门票生成
    [How] 创建活动和孩子，报名
    """
    parent = User(openid="test_enroll")
    db_session.add(parent)
    db_session.commit()

    child = Child(user_id=parent.id, name="小明", age=7, grade="二年级")
    db_session.add(child)
    db_session.commit()

    now = datetime.now()
    activity = Activity(
        title="读书会", type=0, max_participants=30,
        start_time=now + timedelta(days=7),
        end_time=now + timedelta(days=7, hours=2),
        venue_id=1,
    )
    db_session.add(activity)
    db_session.commit()

    enrollment = ActivityEnrollment(
        activity_id=activity.id,
        child_id=child.id,
        ticket_code="TKT001",
    )
    db_session.add(enrollment)
    db_session.commit()

    assert enrollment.id is not None
    assert enrollment.status == ActivityEnrollment.STATUS_PENDING
    assert enrollment.ticket_code == "TKT001"

    # 验证报名人数递增
    activity.current_participants += 1
    db_session.commit()
    assert activity.current_participants == 1


def test_refund_application(db_session):
    """
    [What] 测试退款申请
    [Why] 验证退款申请的状态流转
    [How] 创建订单和退款申请
    """
    parent = User(openid="test_refund")
    child = Child(user_id=1, name="小明", age=7, grade="二年级")
    db_session.add_all([parent, child])
    db_session.commit()
    child.user_id = parent.id
    db_session.commit()

    order = Order(order_no="MW_REFUND", user_id=parent.id, child_id=child.id, type=2, amount=500.00)
    db_session.add(order)
    db_session.commit()

    refund = RefundApplication(
        order_id=order.id,
        user_id=parent.id,
        child_id=child.id,
        amount=order.amount,
        refund_amount=333.33,
        reason="观察期不满意",
        used_days=10,
    )
    db_session.add(refund)
    db_session.commit()

    assert refund.id is not None
    assert refund.status == RefundApplication.STATUS_PENDING
    assert float(refund.refund_amount) == 333.33

    # 审核通过
    refund.status = RefundApplication.STATUS_APPROVED
    db_session.commit()
    assert refund.status == RefundApplication.STATUS_APPROVED

    # 退款完成
    refund.status = RefundApplication.STATUS_COMPLETED
    db_session.commit()
    assert refund.status == RefundApplication.STATUS_COMPLETED
