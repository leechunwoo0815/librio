"""F-074 排班时间校验 — schema 格式/顺序 + service 同老师同日重叠拒绝"""

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.admin.admin_schemas import CreateScheduleRequest
from backend.domain.admin.models import Teacher
from backend.domain.admin.services.teacher_service import AdminTeacherService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_teacher(db) -> Teacher:
    t = Teacher(name="排班老师", phone="13900007400", venue_id=1)
    db.add(t)
    db.commit()
    return t


class TestSchemaValidation:
    def test_bad_hhmm_format_rejected(self):
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                teacher_id=1, weekday=1, start_time="9:00", end_time="10:00"
            )

    def test_invalid_minute_rejected(self):
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                teacher_id=1, weekday=1, start_time="09:60", end_time="10:00"
            )

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError, match="start_time 必须早于"):
            CreateScheduleRequest(
                teacher_id=1, weekday=1, start_time="10:00", end_time="09:00"
            )

    def test_equal_times_rejected(self):
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                teacher_id=1, weekday=1, start_time="10:00", end_time="10:00"
            )

    def test_valid_schedule_ok(self):
        req = CreateScheduleRequest(
            teacher_id=1, weekday=1, start_time="09:00", end_time="10:30"
        )
        assert req.start_time == "09:00"


class TestServiceOverlap:
    def test_overlap_rejected(self, db):
        from backend.common.exceptions import ValidationError as BizValidationError

        teacher = _mk_teacher(db)
        svc = AdminTeacherService(db)
        svc.create_schedule(teacher.id, 1, "09:00", "10:00")
        with pytest.raises(BizValidationError, match="时间重叠"):
            svc.create_schedule(teacher.id, 1, "09:30", "10:30")

    def test_touching_not_overlap(self, db):
        """半开区间：09:00-10:00 与 10:00-11:00 首尾相接不算重叠"""
        teacher = _mk_teacher(db)
        svc = AdminTeacherService(db)
        svc.create_schedule(teacher.id, 1, "09:00", "10:00")
        svc.create_schedule(teacher.id, 1, "10:00", "11:00")
        assert len(svc.get_teacher_schedule(teacher.id)) == 2

    def test_different_weekday_ok(self, db):
        teacher = _mk_teacher(db)
        svc = AdminTeacherService(db)
        svc.create_schedule(teacher.id, 1, "09:00", "10:00")
        svc.create_schedule(teacher.id, 2, "09:00", "10:00")
        assert len(svc.get_teacher_schedule(teacher.id)) == 2
