"""批次5 F-096/F-112 删除保护：有关联数据拒绝删除，引导完整保障链"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.activity.models import Activity, ActivityEnrollment
from backend.domain.activity.service import ActivityService
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.parent_course_time.models import ParentCourseTime
from backend.domain.parent_course_time.service import ParentCourseTimeService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestF096DeleteActivity:
    def test_delete_rejected_with_active_enrollments(self, db):
        from backend.common.exceptions import ConflictError

        user = User(openid="d096", phone="13800009600")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="报", age=7, grade="二年级")
        db.add(child)
        db.commit()
        activity = Activity(
            title="收费活动",
            type=1,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            is_free=0,
        )
        db.add(activity)
        db.commit()
        db.add(
            ActivityEnrollment(
                activity_id=activity.id,
                child_id=child.id,
                ticket_code="T-096-001",
                status=ActivityEnrollment.STATUS_APPROVED,
            )
        )
        db.commit()

        with pytest.raises(ConflictError, match="取消活动"):
            ActivityService(db).delete_activity(activity.id)
        db.refresh(activity)
        assert activity.is_deleted == 0

    def test_delete_ok_without_enrollments(self, db):
        activity = Activity(
            title="空活动",
            type=1,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
        )
        db.add(activity)
        db.commit()
        result = ActivityService(db).delete_activity(activity.id)
        assert result["success"] is True


class TestF112DeleteSlot:
    def test_delete_rejected_with_paid_order(self, db):
        from backend.common.exceptions import ConflictError

        user = User(openid="d112", phone="13800011200")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="课", age=7, grade="二年级")
        db.add(child)
        db.commit()
        slot = ParentCourseTime(
            venue_id=1,
            course_date="2026-08-20",
            start_time="09:00",
            end_time="10:00",
            max_participants=10,
        )
        db.add(slot)
        db.commit()
        db.add(
            Order(
                order_no="MW-PC-112",
                user_id=user.id,
                child_id=child.id,
                type=OrderType.PARENT_COURSE,
                amount=Decimal("99"),
                pay_status=PayStatus.PAID,
                parent_course_time_id=slot.id,
            )
        )
        db.commit()

        with pytest.raises(ConflictError, match="关联订单"):
            ParentCourseTimeService(db).delete(slot.id)
        db.refresh(slot)
        assert slot.is_deleted == 0

    def test_delete_ok_without_orders(self, db):
        slot = ParentCourseTime(
            venue_id=1,
            course_date="2026-08-21",
            start_time="09:00",
            end_time="10:00",
        )
        db.add(slot)
        db.commit()
        result = ParentCourseTimeService(db).delete(slot.id)
        assert result["success"] is True
