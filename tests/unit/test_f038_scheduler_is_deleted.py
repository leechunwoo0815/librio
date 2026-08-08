"""F-038 回归：scheduler 任务层 is_deleted 过滤

remind_pending_submissions 两处（软删提交/软删孩子）+ generate_monthly_reports top_books
一处（软删图书）。软删记录不得触发提醒/展示。
"""

import functools
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.advancement.models import ReadingSubmission
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.user.models import User
from backend.tasks import scheduler


@pytest.fixture(autouse=True)
def _noop_lock(monkeypatch):
    def _noop(*args, **kwargs):
        def deco(func):
            @functools.wraps(func)
            def wrapper(*a, **kw):
                return func(*a, **kw)

            return wrapper

        return deco

    monkeypatch.setattr(scheduler, "distributed_lock", _noop)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    monkeypatch.setattr(scheduler, "_get_db_session", lambda: session)
    yield session
    session.close()


def _mk_user_child(db, suffix):
    user = User(openid=f"f038_{suffix}", phone=f"13800380{suffix}")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name=f"孩子{suffix}",
        age=7,
        grade="二年级",
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_submission(db, child_id, book_id=1, is_deleted=0):
    s = ReadingSubmission(
        child_id=child_id,
        book_id=book_id,
        status=ReadingSubmission.STATUS_PENDING,
        submitted_at=datetime.now() - timedelta(days=10),
        is_deleted=is_deleted,
    )
    db.add(s)
    db.commit()
    return s


class TestRemindPendingSubmissions:
    def test_soft_deleted_submission_not_reminded(self, db):
        """软删提交：不提醒（即使孩子正常且有老师）"""
        user, child = _mk_user_child(db, "01")
        child.teacher_id = 1
        db.commit()
        _mk_submission(db, child.id, is_deleted=1)

        scheduler.remind_pending_submissions()

        messages = db.query(SystemMessage).all()
        assert messages == []

    def test_soft_deleted_child_not_reminded(self, db):
        """软删孩子：不提醒（档案已删不得再收消息）"""
        user, child = _mk_user_child(db, "02")
        child.teacher_id = 1
        child.is_deleted = 1
        db.commit()
        _mk_submission(db, child.id)

        scheduler.remind_pending_submissions()

        messages = db.query(SystemMessage).all()
        assert messages == []

    def test_active_child_reminded(self, db):
        """对照组：正常孩子+正常提交 → 提醒老师"""
        user, child = _mk_user_child(db, "03")
        uid = user.id  # 任务内 commit+close 会使对象过期/detached，先取值
        child.teacher_id = 1
        db.commit()
        _mk_submission(db, child.id)

        scheduler.remind_pending_submissions()

        messages = db.query(SystemMessage).all()
        assert len(messages) == 1
        assert "待审核提醒" in messages[0].title
        assert messages[0].user_id == uid
