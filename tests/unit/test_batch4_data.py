"""批次 4 数据/契约回归：F-059/060/063/069/072/073"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ValidationError
from backend.database import Base
from backend.domain.book.schemas import BookCreate
from backend.domain.child.models import Child
from backend.domain.parent_course_time.schemas import ParentCourseTimeCreate
from backend.domain.parent_course_time.service import ParentCourseTimeService
from backend.domain.reading.models import ReadingSession
from backend.domain.reading.schemas import EndSessionRequest
from backend.domain.reading.service import ReadingService
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
    user = User(openid="b4", phone="13800004001")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="B4", age=7, grade="一")
    db.add(child)
    db.commit()
    return user, child


class TestF059EndSessionGuard:
    def test_duplicate_end_rejected(self, db):
        _, child = _mk_user_child(db)
        session = ReadingSession(
            child_id=child.id,
            book_id=1,
            start_time=datetime.now() - timedelta(minutes=10),
        )
        db.add(session)
        db.commit()
        svc = ReadingService(db)
        svc.end_session(
            session.id,
            EndSessionRequest(pages_read=1, words_read=10, reading_minutes=5),
        )
        with pytest.raises(ValidationError, match="已结束"):
            svc.end_session(
                session.id,
                EndSessionRequest(pages_read=1, words_read=10, reading_minutes=5),
            )


class TestF060EndSessionLimits:
    def test_pages_read_upper_bound(self):
        with pytest.raises(PydanticValidationError):
            EndSessionRequest(pages_read=10001)


class TestF063DeletionCascade:
    def test_assessment_in_delete_list(self):
        from backend.domain.child.deletion_service import DELETE_TABLES_BY_CHILD

        assert "assessment" in DELETE_TABLES_BY_CHILD


class TestF069ParentCourseTime:
    def test_end_after_start_required(self, db):
        svc = ParentCourseTimeService(db)
        with pytest.raises(ValidationError, match="结束时间必须晚于"):
            svc.create(
                ParentCourseTimeCreate(
                    venue_id=1,
                    course_date="2026-08-10",
                    start_time="10:00",
                    end_time="09:00",
                )
            )

    def test_max_participants_ge_1(self):
        with pytest.raises(PydanticValidationError):
            ParentCourseTimeCreate(
                venue_id=1,
                course_date="2026-08-10",
                start_time="09:00",
                end_time="10:00",
                max_participants=0,
            )

    def test_overlap_same_venue_same_day_rejected(self, db):
        """F-069 终审：同日同 venue 时间重叠必须拒绝"""
        from backend.domain.parent_course_time.models import ParentCourseTime

        db.add(
            ParentCourseTime(
                venue_id=7,
                course_date="2026-08-10",
                start_time="10:00",
                end_time="11:00",
                max_participants=10,
            )
        )
        db.commit()

        svc = ParentCourseTimeService(db)
        with pytest.raises(ValidationError, match="重叠"):
            svc.create(
                ParentCourseTimeCreate(
                    venue_id=7,
                    course_date="2026-08-10",
                    start_time="10:30",
                    end_time="11:30",
                )
            )

    def test_adjacent_and_other_venue_allowed(self, db):
        """F-069：首尾相接（无重叠）与不同场馆同时间均允许"""
        from backend.domain.parent_course_time.models import ParentCourseTime

        db.add(
            ParentCourseTime(
                venue_id=7,
                course_date="2026-08-10",
                start_time="10:00",
                end_time="11:00",
                max_participants=10,
            )
        )
        db.commit()
        svc = ParentCourseTimeService(db)

        svc.create(
            ParentCourseTimeCreate(
                venue_id=7,
                course_date="2026-08-10",
                start_time="11:00",
                end_time="12:00",
            )
        )
        svc.create(
            ParentCourseTimeCreate(
                venue_id=8,
                course_date="2026-08-10",
                start_time="10:30",
                end_time="11:30",
            )
        )

    def test_update_overlap_rejected_excluding_self(self, db):
        """F-069：update 撞到其他时段拒绝；仅重叠自身（时间不变）放行"""
        from backend.domain.parent_course_time.models import ParentCourseTime
        from backend.domain.parent_course_time.schemas import ParentCourseTimeUpdate

        slot = ParentCourseTime(
            venue_id=7,
            course_date="2026-08-10",
            start_time="10:00",
            end_time="11:00",
            max_participants=10,
        )
        other = ParentCourseTime(
            venue_id=7,
            course_date="2026-08-10",
            start_time="11:00",
            end_time="12:00",
            max_participants=10,
        )
        db.add_all([slot, other])
        db.commit()

        svc = ParentCourseTimeService(db)
        with pytest.raises(ValidationError, match="重叠"):
            svc.update(slot.id, ParentCourseTimeUpdate(end_time="11:30"))
        # 自身不重叠（更新无关字段）
        svc.update(slot.id, ParentCourseTimeUpdate(max_participants=12))


class TestF073BookCreateCrossValidation:
    def test_age_min_le_age_max(self):
        with pytest.raises(PydanticValidationError, match="age_min"):
            BookCreate(
                isbn="9781234567890",
                title="书",
                author="A",
                ar_value=Decimal("2.0"),
                age_min=10,
                age_max=5,
            )

    def test_isbn_format_validated(self):
        """F-073 终审：ISBN 必须为 10/13 位数字或带连字符标准形式"""
        BookCreate(
            isbn="9781234567890",
            title="书",
            author="A",
            ar_value=Decimal("2.0"),
            age_min=3,
            age_max=5,
        )
        BookCreate(
            isbn="978-7-121-12345-6",
            title="书",
            author="A",
            ar_value=Decimal("2.0"),
            age_min=3,
            age_max=5,
        )
        with pytest.raises(PydanticValidationError, match="isbn"):
            BookCreate(
                isbn="NOT-A-ISBN",
                title="书",
                author="A",
                ar_value=Decimal("2.0"),
                age_min=3,
                age_max=5,
            )
