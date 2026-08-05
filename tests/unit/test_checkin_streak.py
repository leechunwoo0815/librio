# tests/unit/test_checkin_streak.py
"""打卡事件 → 连续打卡天数（streak）——自然日语义

PRD §10.1：打卡日历显示"当前连续打卡天数 / 最长连续打卡天数"——连续指自然日连续。
此前 handler 每次打卡 +1：同日 4 类型打卡会 +4，断签不重置，展示端/观察期报告
读到错误中间值（对账任务凌晨 3:45 才修正）。本测试钉死自然日口径。
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.reading.models import CheckIn
from backend.domain.user.models import User
from backend.events.misc_handlers import handle_checkin_for_child_streak
from backend.common.events import CheckInEvent


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mk_child(db, **stats):
    u = User(openid=f"ckin_{uuid.uuid4().hex[:8]}", parent_name="测试家长")
    db.add(u)
    db.flush()
    c = Child(user_id=u.id, name="测试孩子", age=5, grade="中班", **stats)
    db.add(c)
    db.flush()
    return c


def _checkin(db, child_id, check_date, check_type=1):
    db.add(
        CheckIn(
            child_id=child_id,
            check_date=check_date,
            check_type=check_type,
        )
    )
    db.flush()


def _fire(db, child_id):
    handle_checkin_for_child_streak(
        CheckInEvent(child_id=child_id, streak_days=0), db=db
    )
    db.commit()


class TestCheckinStreak:
    def test_same_day_four_types_streak_1(self, db):
        """同日 4 类型打卡 → streak=1（自然日计 1，不叠加为 4）"""
        c = _mk_child(db)
        today = date.today()
        _checkin(db, c.id, today, 1)
        _checkin(db, c.id, today, 2)
        _checkin(db, c.id, today, 3)
        _checkin(db, c.id, today, 4)
        _fire(db, c.id)
        _fire(db, c.id)
        _fire(db, c.id)
        _fire(db, c.id)
        db.refresh(c)
        assert c.current_streak_days == 1
        assert c.longest_streak_days == 1

    def test_yesterday_plus_today_streak_2(self, db):
        """昨天打卡 + 今天打卡 → streak=2"""
        c = _mk_child(db)
        today = date.today()
        _checkin(db, c.id, today - timedelta(days=1))
        _checkin(db, c.id, today)
        _fire(db, c.id)
        db.refresh(c)
        assert c.current_streak_days == 2

    def test_gap_breaks_streak(self, db):
        """前天打卡 + 今天打卡（昨天断签）→ streak=1"""
        c = _mk_child(db)
        today = date.today()
        _checkin(db, c.id, today - timedelta(days=2))
        _checkin(db, c.id, today)
        _fire(db, c.id)
        db.refresh(c)
        assert c.current_streak_days == 1

    def test_longest_grows_on_consecutive(self, db):
        """连续 3 天（3天前/2天前/昨天）+ 今天 → current=4，longest=4"""
        c = _mk_child(db)
        today = date.today()
        for i in range(3, 0, -1):
            _checkin(db, c.id, today - timedelta(days=i))
        _checkin(db, c.id, today)
        _fire(db, c.id)
        db.refresh(c)
        assert c.current_streak_days == 4
        assert c.longest_streak_days == 4

    def test_current_resets_longest_kept(self, db):
        """2天前+3天前（连续2天，longest=2），昨天断签，今天打卡 → current=1，longest=2"""
        c = _mk_child(db)
        today = date.today()
        _checkin(db, c.id, today - timedelta(days=3))
        _checkin(db, c.id, today - timedelta(days=2))
        _checkin(db, c.id, today)
        _fire(db, c.id)
        db.refresh(c)
        assert c.current_streak_days == 1  # 昨天（today-1）无打卡 → 断签重置
        assert c.longest_streak_days == 2  # 3天前+2天前连续段保留
