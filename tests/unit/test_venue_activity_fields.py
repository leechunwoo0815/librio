# tests/unit/test_venue_activity_fields.py
"""批次6 后端新增字段覆盖：venue 公开端点 / activity my_enrollment / deposit fine 字段"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import DepositStatus
from backend.database import Base
from backend.domain.activity.models import Activity, ActivityEnrollment
from backend.domain.activity.service import ActivityService
from backend.domain.admin.models import Venue
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.deposit.service import DepositService
from backend.domain.user.models import User


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def user(db):
    u = User(openid=f"test_openid_{uuid.uuid4().hex[:8]}", parent_name="测试家长")
    db.add(u)
    db.flush()
    db.refresh(u)
    return u


@pytest.fixture
def child(db, user):
    c = Child(user_id=user.id, name="测试孩子", age=5, grade="中班")
    db.add(c)
    db.flush()
    db.refresh(c)
    return c


class TestVenuePublicList:
    def test_public_list_only_active(self, db):
        db.add(Venue(name="人广馆", address="南京东路800号", status="active"))
        db.add(Venue(name="关闭馆", address="x路1号", status="inactive"))
        db.flush()
        from backend.domain.venue.router import list_public_venues

        result = list_public_venues(db)
        names = [v["name"] for v in result]
        assert "人广馆" in names
        assert "关闭馆" not in names
        assert all(
            set(v.keys()) == {"id", "name", "address", "phone", "business_hours"}
            for v in result
        )


class TestActivityMyEnrollment:
    def _make_activity(self, db):
        from datetime import datetime, timedelta

        now = datetime.now()
        a = Activity(
            title="读书会",
            type=1,
            status=1,
            start_time=now + timedelta(days=7),
            end_time=now + timedelta(days=7, hours=2),
            max_participants=20,
            current_participants=1,
        )
        db.add(a)
        db.flush()
        db.refresh(a)
        return a

    def test_my_enrollment_attached(self, db, child):
        activity = self._make_activity(db)
        enr = ActivityEnrollment(
            activity_id=activity.id,
            child_id=child.id,
            ticket_code=uuid.uuid4().hex[:8],
            status=ActivityEnrollment.STATUS_APPROVED,
        )
        db.add(enr)
        db.flush()

        resp = ActivityService(db).get_activity(activity.id, child_id=child.id)
        assert resp.my_enrollment_id == enr.id
        assert resp.my_enrollment_status == ActivityEnrollment.STATUS_APPROVED
        assert resp.my_ticket_code == enr.ticket_code

    def test_no_enrollment_fields_none(self, db, child):
        activity = self._make_activity(db)
        resp = ActivityService(db).get_activity(activity.id, child_id=child.id)
        assert resp.my_enrollment_id is None
        assert resp.my_enrollment_status is None

    def test_list_attach_only_own_child(self, db, child, user):
        activity = self._make_activity(db)
        other_child = Child(user_id=user.id, name="别人娃", age=6, grade="大班")
        db.add(other_child)
        db.flush()
        enr = ActivityEnrollment(
            activity_id=activity.id,
            child_id=other_child.id,
            ticket_code=uuid.uuid4().hex[:8],
            status=1,
        )
        db.add(enr)
        db.flush()

        results = ActivityService(db).list_activities(child_id=child.id)
        target = [r for r in results if r.id == activity.id][0]
        assert target.my_enrollment_id is None


class TestDepositStatusFineField:
    def test_unpaid_returns_config_amount_and_fine(self, db, child):
        child.outstanding_fines = Decimal("0")
        db.flush()
        result = DepositService(db).get_deposit_status(child.id)
        assert result["status"] == 0
        assert Decimal(result["amount"]) > 0  # 配置押金金额（非 0）
        assert result["fine"] == "0"

    def test_paid_includes_outstanding_fines(self, db, child):
        child.outstanding_fines = Decimal("15.50")
        record = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200"),
            status=DepositStatus.PAID,
        )
        db.add(record)
        db.flush()
        result = DepositService(db).get_deposit_status(child.id)
        assert result["status"] == DepositStatus.PAID
        assert result["fine"] == "15.50"
