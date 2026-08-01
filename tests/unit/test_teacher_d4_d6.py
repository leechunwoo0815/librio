# tests/unit/test_teacher_d4_d6.py
"""批次8 单元测试 — D4 达标自动审核 / D1 老师工作台 / D2 课后反馈 / D6 报告转化"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
import backend.domain.evaluation.models  # noqa: F401 — guidance_record 等表注册
from backend.bootstrap import register_event_handlers
from backend.common.events import QuizPassedEvent
from backend.common.exceptions import ForbiddenError
from backend.database import Base
from backend.domain.admin.models import Teacher, TeacherSchedule
from backend.domain.admin.services.teacher_workbench_service import (
    TeacherWorkbenchService,
)
from backend.domain.advancement.models import ReadingSubmission
from backend.domain.book.models import Book
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.reading.models import ReadingSession
from backend.domain.user.models import User
from backend.events.quiz_handlers import handle_quiz_passed_for_submission


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


def _mk(db):
    user = User(openid="t8", phone="13800000701")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="小明",
        age=7,
        grade="二年级",
        status=1,
        member_start_time=datetime.now() - timedelta(days=46),
    )
    db.add(child)
    db.commit()
    book = Book(
        isbn="T8001",
        title="书",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=1000,
    )
    db.add(book)
    db.commit()
    return user, child, book


def _mk_pending_sub(db, child, book, minutes=0):
    sub = ReadingSubmission(
        child_id=child.id,
        book_id=book.id,
        word_count=1000,
        status=ReadingSubmission.STATUS_PENDING,
    )
    db.add(sub)
    if minutes:
        session = ReadingSession(
            child_id=child.id,
            book_id=book.id,
            start_time=datetime.now() - timedelta(hours=2),
            end_time=datetime.now() - timedelta(hours=1),
            duration_seconds=minutes * 60,
        )
        db.add(session)
    db.commit()
    return sub


def _quiz_event(child, book):
    return QuizPassedEvent(child_id=child.id, book_id=book.id, word_count=1000)


class TestD4AutoApprove:
    def test_quiz_pass_with_enough_minutes_auto_approves(self, db):
        _, child, book = _mk(db)
        sub = _mk_pending_sub(db, child, book, minutes=12)
        handle_quiz_passed_for_submission(_quiz_event(child, book), db)
        db.commit()
        db.refresh(sub)
        assert sub.status == ReadingSubmission.STATUS_APPROVED
        assert sub.reviewed_at is not None

    def test_quiz_pass_without_minutes_stays_pending(self, db):
        """时长不足 → 转人工队列"""
        _, child, book = _mk(db)
        sub = _mk_pending_sub(db, child, book, minutes=3)
        handle_quiz_passed_for_submission(_quiz_event(child, book), db)
        db.refresh(sub)
        assert sub.status == ReadingSubmission.STATUS_PENDING

    def test_no_submission_noop(self, db):
        _, child, book = _mk(db)
        # 无提交时处理器静默返回
        handle_quiz_passed_for_submission(_quiz_event(child, book), db)


class TestD1Workbench:
    def _mk_teacher(self, db):
        teacher = Teacher(name="王老师", phone="13900000001", venue_id=1)
        db.add(teacher)
        db.commit()
        db.add(
            TeacherSchedule(
                teacher_id=teacher.id,
                weekday=date.today().isoweekday(),
                start_time="10:00",
                end_time="11:00",
            )
        )
        db.commit()
        return teacher

    def test_workbench_aggregates(self, db):
        teacher = self._mk_teacher(db)
        _, child, book = _mk(db)
        child.teacher_id = teacher.id
        db.commit()
        _mk_pending_sub(db, child, book)

        svc = TeacherWorkbenchService(db)
        result = svc.get_workbench(teacher.id)
        assert result["teacher"]["name"] == "王老师"
        assert len(result["today_schedules"]) == 1
        assert result["pending_submissions_count"] == 1
        assert result["children_count"] == 1
        assert result["children"][0]["name"] == "小明"


class TestD2Feedback:
    def test_post_feedback_creates_guidance_and_message(self, db):
        teacher = Teacher(name="王老师", phone="13900000001", venue_id=1)
        db.add(teacher)
        db.commit()
        user, child, _ = _mk(db)
        child.teacher_id = teacher.id
        db.commit()

        svc = TeacherWorkbenchService(db)
        result = svc.post_feedback(teacher.id, child.id, "今天表现很棒！", admin_id=1)
        assert result["success"] is True

        msg = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == user.id, SystemMessage.msg_type == 4)
            .first()
        )
        assert msg is not None
        assert "王老师" in msg.title
        assert "表现很棒" in msg.content

    def test_feedback_rejects_other_teachers_child(self, db):
        teacher = Teacher(name="王老师", phone="13900000001", venue_id=1)
        db.add(teacher)
        db.commit()
        user, child, _ = _mk(db)  # child.teacher_id = None
        svc = TeacherWorkbenchService(db)
        with pytest.raises(ForbiddenError, match="本人负责"):
            svc.post_feedback(teacher.id, child.id, "X", admin_id=1)


class TestD6ReportEnrichment:
    def test_report_contains_d6_fields(self, db):
        from backend.domain.report.service import ReportService

        user, child, book = _mk(db)
        child.current_streak_days = 7
        db.commit()
        # 一条已通过提交（读完 1 本）
        sub = ReadingSubmission(
            child_id=child.id,
            book_id=book.id,
            word_count=1000,
            status=ReadingSubmission.STATUS_APPROVED,
            submitted_at=datetime.now() - timedelta(days=10),
        )
        db.add(sub)
        db.commit()

        svc = ReportService(db)
        results = svc.generate_due_reports()
        assert len(results) == 1
        report = svc.get_report(child.id)
        assert report["total_books_read"] == 1
        assert report["streak_days"] == 7
        assert report["cta_text"] is not None
        assert "连续打卡 7 天" in report["cta_text"]
        assert "续费" in report["cta_text"]
