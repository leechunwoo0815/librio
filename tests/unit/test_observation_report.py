# tests/unit/test_observation_report.py
"""观察期报告服务测试"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.advancement.models import Level, ChildLevel, ReadingSubmission, Quiz
from backend.domain.report.models import ObservationReport
from backend.domain.report.service import ReportService, OBSERVATION_DAYS


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup(db, observation_days=31):
    """创建测试数据"""
    user = User(openid="obs_user", phone="13800138003")
    db.add(user); db.commit()

    child = Child(
        user_id=user.id, name="观察期小明", age=6, grade="一年级",
        english_name="Tom", status=Child.STATUS_OBSERVATION,
        create_time=datetime.now() - timedelta(days=observation_days),
        member_start_time=datetime.now() - timedelta(days=observation_days),
    )
    db.add(child); db.commit()

    level = Level(name="A", sort_order=1, required_books=10, max_borrow_count=20)
    db.add(level); db.commit()

    cl = ChildLevel(child_id=child.id, level_id=level.id, is_current=True)
    db.add(cl); db.commit()

    return user, child, level


def test_generate_report_for_due_child(db):
    """30天到期自动生成报告"""
    user, child, level = _setup(db, observation_days=31)

    svc = ReportService(db)
    results = svc.generate_due_reports()
    assert len(results) == 1
    assert results[0]["child_id"] == child.id


def test_no_report_for_not_due_child(db):
    """未满30天不生成报告"""
    user, child, level = _setup(db, observation_days=15)

    svc = ReportService(db)
    results = svc.generate_due_reports()
    assert len(results) == 0


def test_no_duplicate_report(db):
    """已生成报告的孩子不重复生成"""
    user, child, level = _setup(db, observation_days=31)

    svc = ReportService(db)
    svc.generate_due_reports()
    results = svc.generate_due_reports()
    assert len(results) == 0


def test_report_contains_reading_stats(db):
    """报告包含阅读统计"""
    user, child, level = _setup(db, observation_days=31)

    # 添加阅读提交记录
    book = Book(isbn="978OBS1", title="ObsBook", author="A", ar_value=2.0,
                age_min=5, age_max=9, word_count=3000)
    db.add(book); db.commit()

    for i in range(5):
        sub = ReadingSubmission(
            child_id=child.id, book_id=book.id,
            status=ReadingSubmission.STATUS_APPROVED,
            submitted_at=datetime.now() - timedelta(days=10),
            word_count=3000,
        )
        db.add(sub)
    db.commit()

    svc = ReportService(db)
    svc.generate_due_reports()

    report = svc.get_report(child.id)
    assert report is not None
    assert report["total_books_read"] == 5
    assert report["total_words_read"] == 15000


def test_report_contains_quiz_stats(db):
    """报告包含测验统计"""
    user, child, level = _setup(db, observation_days=31)

    book = Book(isbn="978OBS2", title="QuizBook", author="B", ar_value=2.0,
                age_min=5, age_max=9, word_count=2000)
    db.add(book); db.commit()

    # 3次测验，2次通过
    for i, (score, status) in enumerate([(90, Quiz.STATUS_COMPLETED), (60, Quiz.STATUS_COMPLETED), (85, Quiz.STATUS_COMPLETED)]):
        quiz = Quiz(
            child_id=child.id, book_id=book.id,
            status=status, score=score, total_questions=5,
            create_time=datetime.now() - timedelta(days=10),
        )
        db.add(quiz)
    db.commit()

    svc = ReportService(db)
    svc.generate_due_reports()

    report = svc.get_report(child.id)
    assert report["quizzes_attempted"] == 3
    assert report["quizzes_passed"] == 2  # 90和85通过(>=80)


def test_report_contains_teacher_comment(db):
    """老师可以添加评语"""
    user, child, level = _setup(db, observation_days=31)

    svc = ReportService(db)
    svc.generate_due_reports()

    report = svc.get_report(child.id)
    report_id = report["id"]

    updated = svc.add_teacher_comment(report_id, teacher_id=1, comment="表现优秀")
    assert updated["teacher_comment"] == "表现优秀"
    assert updated["teacher_id"] == 1


def test_get_report_returns_none_when_absent(db):
    """没有报告时返回None"""
    user, child, level = _setup(db, observation_days=31)

    svc = ReportService(db)
    report = svc.get_report(child.id)
    assert report is None


def test_mark_report_viewed(db):
    """标记报告已查看"""
    user, child, level = _setup(db, observation_days=31)

    svc = ReportService(db)
    svc.generate_due_reports()

    report = svc.get_report(child.id)
    assert report["status"] == ObservationReport.STATUS_GENERATED

    svc.mark_viewed(report["id"])
    updated = svc.get_report(child.id)
    assert updated["status"] == ObservationReport.STATUS_VIEWED
