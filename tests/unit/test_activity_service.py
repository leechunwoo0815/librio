"""Activity service unit tests — coverage for core paths"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.database import Base
from backend.domain.activity.service import ActivityService
from backend.domain.activity.schemas import ActivityEnrollRequest
from backend.domain.activity.models import Activity, ActivityEnrollment
from backend.common.exceptions import (
    NotFoundError,
    ConflictError,
    ValidationError,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_activity(
    db: Session,
    title="test activity",
    is_free=1,
    max_participants=10,
    current_participants=0,
    status=Activity.STATUS_ENROLLING,
    price=None,
    start_time=None,
):
    a = Activity(
        title=title,
        type=Activity.TYPE_READING,
        is_free=is_free,
        max_participants=max_participants,
        current_participants=current_participants,
        status=status,
        start_time=start_time or (datetime.now() + timedelta(hours=48)),
        end_time=(datetime.now() + timedelta(hours=50)),
        price=price,
    )
    db.add(a)
    db.flush()
    return a


_enrollment_counter = 0


def _create_enrollment(
    db: Session,
    activity_id,
    child_id=1,
    ticket_code=None,
    status=ActivityEnrollment.STATUS_PENDING,
):
    global _enrollment_counter
    _enrollment_counter += 1
    if ticket_code is None:
        ticket_code = f"TICKET{_enrollment_counter:04d}"
    e = ActivityEnrollment(
        activity_id=activity_id,
        child_id=child_id,
        ticket_code=ticket_code,
        status=status,
    )
    db.add(e)
    db.flush()
    return e


class TestListActivities:
    def test_list_activities_empty(self, db):
        svc = ActivityService(db)
        result = svc.list_activities(page=1, page_size=20)
        assert result == []

    def test_list_activities_with_data(self, db):
        _create_activity(db)
        db.commit()
        svc = ActivityService(db)
        result = svc.list_activities(page=1, page_size=20)
        assert len(result) == 1
        assert result[0].title == "test activity"

    def test_list_with_count_pagination(self, db):
        for i in range(5):
            _create_activity(db, title=f"Activity {i}")
        db.commit()
        svc = ActivityService(db)
        result = svc.list_with_count(page=1, page_size=2)
        assert result["total"] == 5
        assert len(result["items"]) == 2
        assert result["has_next"] is True


class TestGetActivity:
    def test_get_activity_ok(self, db):
        a = _create_activity(db)
        db.commit()
        svc = ActivityService(db)
        result = svc.get_activity(a.id)
        assert result.id == a.id
        assert result.title == "test activity"

    def test_get_activity_not_found(self, db):
        svc = ActivityService(db)
        with pytest.raises(NotFoundError):
            svc.get_activity(999)


class TestEnroll:
    def test_enroll_success_free(self, db):
        a = _create_activity(db, is_free=1)
        db.commit()
        svc = ActivityService(db)
        data = ActivityEnrollRequest(child_id=1, activity_id=a.id)
        result = svc.enroll(data)
        assert result["status"] == "enrolled"
        assert result["ticket_code"].startswith("ACT-")
        # free activity should auto-approve
        enrollment = (
            db.query(ActivityEnrollment).filter_by(activity_id=a.id, child_id=1).first()
        )
        assert enrollment.status == ActivityEnrollment.STATUS_APPROVED

    def test_enroll_success_paid(self, db):
        a = _create_activity(db, is_free=0, price=Decimal("50.00"))
        db.commit()
        svc = ActivityService(db)
        data = ActivityEnrollRequest(child_id=1, activity_id=a.id)
        result = svc.enroll(data)
        assert result["status"] == "enrolled"
        enrollment = (
            db.query(ActivityEnrollment).filter_by(activity_id=a.id, child_id=1).first()
        )
        # paid enrollment stays PENDING
        assert enrollment.status == ActivityEnrollment.STATUS_PENDING

    def test_enroll_already_enrolled(self, db):
        a = _create_activity(db)
        _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        db.commit()
        svc = ActivityService(db)
        data = ActivityEnrollRequest(child_id=1, activity_id=a.id)
        result = svc.enroll(data)
        assert result["status"] == "already_enrolled"

    def test_enroll_already_cancelled_re_enroll(self, db):
        a = _create_activity(db)
        _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_CANCELLED
        )
        db.commit()
        svc = ActivityService(db)
        data = ActivityEnrollRequest(child_id=1, activity_id=a.id)
        result = svc.enroll(data)
        assert result["status"] == "enrolled"

    def test_enroll_wrong_activity_status(self, db):
        a = _create_activity(db, status=Activity.STATUS_DRAFT)
        db.commit()
        svc = ActivityService(db)
        data = ActivityEnrollRequest(child_id=1, activity_id=a.id)
        with pytest.raises(ValidationError, match="该活动不在报名中"):
            svc.enroll(data)

    def test_enroll_full_capacity(self, db):
        a = _create_activity(db, max_participants=1, current_participants=1)
        db.commit()
        svc = ActivityService(db)
        data = ActivityEnrollRequest(child_id=1, activity_id=a.id)
        with pytest.raises(ValidationError, match="报名人数已满"):
            svc.enroll(data)

    def test_enroll_no_max_limit(self, db):
        a = _create_activity(db, max_participants=0)
        db.commit()
        svc = ActivityService(db)
        data = ActivityEnrollRequest(child_id=1, activity_id=a.id)
        result = svc.enroll(data)
        assert result["status"] == "enrolled"


class TestCancelEnrollment:
    def test_cancel_success(self, db):
        a = _create_activity(db, start_time=datetime.now() + timedelta(hours=48))
        e = _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.cancel_enrollment(e.id)
        assert result["status"] == ActivityEnrollment.STATUS_CANCELLED

    def test_cancel_not_found(self, db):
        svc = ActivityService(db)
        with pytest.raises(NotFoundError):
            svc.cancel_enrollment(999)

    def test_cancel_already_cancelled(self, db):
        a = _create_activity(db)
        e = _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_CANCELLED
        )
        db.commit()
        svc = ActivityService(db)
        with pytest.raises(ConflictError, match="已取消"):
            svc.cancel_enrollment(e.id)


class TestSignIn:
    def test_sign_in_success(self, db):
        a = _create_activity(db, status=Activity.STATUS_IN_PROGRESS)
        e = _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.sign_in(e.id)
        assert result["status"] == ActivityEnrollment.STATUS_SIGNED_IN

    def test_sign_in_not_found(self, db):
        svc = ActivityService(db)
        with pytest.raises(NotFoundError):
            svc.sign_in(999)

    def test_sign_in_wrong_activity_status(self, db):
        a = _create_activity(db, status=Activity.STATUS_DRAFT)
        e = _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        db.commit()
        svc = ActivityService(db)
        with pytest.raises(ValidationError, match="活动未在进行中"):
            svc.sign_in(e.id)

    def test_sign_in_cancelled_enrollment(self, db):
        a = _create_activity(db, status=Activity.STATUS_IN_PROGRESS)
        e = _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_CANCELLED
        )
        db.commit()
        svc = ActivityService(db)
        with pytest.raises(ConflictError, match="当前状态不可签到"):
            svc.sign_in(e.id)


class TestSignInByTicketCode:
    def test_sign_in_by_ticket_success(self, db):
        a = _create_activity(db, status=Activity.STATUS_IN_PROGRESS)
        _create_enrollment(
            db,
            a.id,
            child_id=1,
            ticket_code="SCAN001",
            status=ActivityEnrollment.STATUS_APPROVED,
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.sign_in_by_ticket_code("SCAN001")
        assert result["status"] == ActivityEnrollment.STATUS_SIGNED_IN

    def test_sign_in_by_ticket_not_found(self, db):
        svc = ActivityService(db)
        with pytest.raises(NotFoundError, match="签到码对应的报名记录不存在"):
            svc.sign_in_by_ticket_code("NONEXIST")

    def test_sign_in_by_ticket_cancelled(self, db):
        _create_enrollment(
            db,
            1,
            child_id=1,
            ticket_code="CANCELLED",
            status=ActivityEnrollment.STATUS_CANCELLED,
        )
        db.commit()
        svc = ActivityService(db)
        with pytest.raises(ConflictError, match="报名已取消，不可签到"):
            svc.sign_in_by_ticket_code("CANCELLED")

    def test_sign_in_by_ticket_already_signed(self, db):
        _create_enrollment(
            db,
            1,
            child_id=1,
            ticket_code="DONE",
            status=ActivityEnrollment.STATUS_SIGNED_IN,
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.sign_in_by_ticket_code("DONE")
        assert result["message"] == "已签到"


class TestGetEnrollments:
    def test_get_enrollments_empty(self, db):
        svc = ActivityService(db)
        result = svc.get_enrollments(1)
        assert result == []

    def test_get_enrollments_with_data(self, db):
        from backend.domain.child.models import Child
        from backend.domain.user.models import User

        u = User(openid="parent1", phone="13800138001", parent_name="测试家长")
        db.add(u)
        db.flush()
        c = Child(
            name="测试孩子",
            english_name="Test",
            user_id=u.id,
            status=2,
            age=8,
            grade="3",
        )
        db.add(c)
        db.flush()
        a = _create_activity(db)
        _create_enrollment(db, a.id, child_id=c.id, ticket_code="T1")
        db.commit()
        svc = ActivityService(db)
        result = svc.get_enrollments(a.id)
        assert len(result) == 1
        assert result[0]["child_name"] == "测试孩子"
        assert result[0]["parent_name"] == "测试家长"

    def test_get_enrollments_child_deleted(self, db):
        """child deleted should show '未知'"""
        a = _create_activity(db)
        _create_enrollment(db, a.id, child_id=999, ticket_code="T2")
        db.commit()
        svc = ActivityService(db)
        result = svc.get_enrollments(a.id)
        assert len(result) == 1
        assert result[0]["child_name"] == "未知"


class TestBatchCheckin:
    def test_batch_checkin_all_success(self, db):
        a = _create_activity(db)
        _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        _create_enrollment(
            db, a.id, child_id=2, status=ActivityEnrollment.STATUS_APPROVED
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.batch_checkin(a.id, [1, 2])
        assert result["signed_count"] == 2
        assert result["total"] == 2

    def test_batch_checkin_partial(self, db):
        a = _create_activity(db)
        _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.batch_checkin(a.id, [1, 999])
        assert result["signed_count"] == 1
        assert result["total"] == 2
        assert len(result["errors"]) == 1
        assert result["errors"][0]["child_id"] == 999


class TestConfirmPaidEnrollment:
    def test_confirm_success(self, db):
        a = _create_activity(db, is_free=0)
        e = _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_PENDING
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.confirm_paid_enrollment(e.id)
        assert result["status"] == ActivityEnrollment.STATUS_APPROVED

    def test_confirm_not_found(self, db):
        svc = ActivityService(db)
        with pytest.raises(NotFoundError):
            svc.confirm_paid_enrollment(999)

    def test_confirm_wrong_status(self, db):
        a = _create_activity(db, is_free=0)
        e = _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        db.commit()
        svc = ActivityService(db)
        with pytest.raises(ConflictError, match="报名状态"):
            svc.confirm_paid_enrollment(e.id)


class TestCancelActivity:
    def test_cancel_activity_ok(self, db):
        a = _create_activity(db, is_free=1)
        _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.cancel_activity(a.id, admin_id=1)
        assert result["cancelled_enrollments"] == 1
        assert result["refund_applications"] == 0
        db.refresh(a)
        assert a.status == Activity.STATUS_CANCELLED

    def test_cancel_activity_not_found(self, db):
        svc = ActivityService(db)
        with pytest.raises(NotFoundError):
            svc.cancel_activity(999, admin_id=1)

    def test_cancel_activity_already_cancelled(self, db):
        a = _create_activity(db, status=Activity.STATUS_CANCELLED)
        db.commit()
        svc = ActivityService(db)
        with pytest.raises(ConflictError, match="活动已取消"):
            svc.cancel_activity(a.id, admin_id=1)

    def test_cancel_activity_finished(self, db):
        a = _create_activity(db, status=Activity.STATUS_FINISHED)
        db.commit()
        svc = ActivityService(db)
        with pytest.raises(ConflictError, match="活动已结束"):
            svc.cancel_activity(a.id, admin_id=1)

    def test_cancel_activity_multiple_enrollments(self, db):
        a = _create_activity(db, is_free=1)
        _create_enrollment(
            db, a.id, child_id=1, status=ActivityEnrollment.STATUS_APPROVED
        )
        _create_enrollment(
            db, a.id, child_id=2, status=ActivityEnrollment.STATUS_PENDING
        )
        db.commit()
        svc = ActivityService(db)
        result = svc.cancel_activity(a.id, admin_id=1)
        db.refresh(a)
        assert a.status == Activity.STATUS_CANCELLED
        assert result["cancelled_enrollments"] == 2


class TestCRUD:
    def test_create_activity(self, db):
        data = MagicMock()
        data.model_dump.return_value = {
            "title": "New Activity",
            "type": Activity.TYPE_READING,
            "is_free": 1,
            "start_time": datetime.now() + timedelta(hours=24),
            "end_time": datetime.now() + timedelta(hours=26),
            "max_participants": 30,
        }
        svc = ActivityService(db)
        result = svc.create_activity(data)
        assert result["message"] == "活动创建成功"
        assert result["id"] > 0

    def test_update_activity_not_found(self, db):
        data = MagicMock()
        data.model_dump.return_value = {"title": "Updated"}
        svc = ActivityService(db)
        with pytest.raises(NotFoundError):
            svc.update_activity(999, data)

    def test_update_activity_ok(self, db):
        a = _create_activity(db)
        db.commit()
        data = MagicMock()
        data.model_dump.return_value = {"title": "Updated"}
        svc = ActivityService(db)
        result = svc.update_activity(a.id, data)
        assert result["success"] is True
        db.refresh(a)
        assert a.title == "Updated"

    def test_delete_activity_not_found(self, db):
        svc = ActivityService(db)
        with pytest.raises(NotFoundError):
            svc.delete_activity(999)

    def test_delete_activity_ok(self, db):
        a = _create_activity(db)
        db.commit()
        svc = ActivityService(db)
        result = svc.delete_activity(a.id)
        assert result["success"] is True
        db.refresh(a)
        assert a.is_deleted == 1
