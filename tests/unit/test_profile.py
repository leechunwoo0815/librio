# tests/unit/test_profile.py
"""个人名片服务测试"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.advancement.models import Level, ChildLevel, Achievement, ChildAchievement
from backend.domain.profile.service import ProfileService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup(db):
    user = User(openid="profile_user", phone="13800138005")
    db.add(user); db.commit()

    child = Child(user_id=user.id, name="小明", age=7, grade="二年级",
                  english_name="Tom", status=Child.STATUS_OFFICIAL,
                  total_words_read=30000, total_books_finished=10,
                  current_streak_days=15, longest_streak_days=20)
    db.add(child); db.commit()

    level = Level(name="A", sort_order=1, required_books=10,
                  max_borrow_count=20, badge_emoji="🌱")
    db.add(level); db.commit()

    cl = ChildLevel(child_id=child.id, level_id=level.id, is_current=True)
    db.add(cl); db.commit()

    return user, child, level, cl


def test_get_profile_basic(db):
    """名片包含基本信息"""
    user, child, level, cl = _setup(db)
    svc = ProfileService(db)
    profile = svc.get_profile(child.id)

    assert profile is not None
    assert profile["name"] == "小明"
    assert profile["english_name"] == "Tom"
    assert profile["age"] == 7
    assert profile["grade"] == "二年级"


def test_get_profile_reading_stats(db):
    """名片包含阅读统计"""
    user, child, level, cl = _setup(db)
    svc = ProfileService(db)
    profile = svc.get_profile(child.id)

    assert profile["total_books_finished"] == 10
    assert profile["total_words_read"] == 30000
    assert profile["current_streak_days"] == 15
    assert profile["longest_streak_days"] == 20


def test_get_profile_level(db):
    """名片包含当前级别"""
    user, child, level, cl = _setup(db)
    svc = ProfileService(db)
    profile = svc.get_profile(child.id)

    assert profile["current_level"] is not None
    assert profile["current_level"]["level_name"] == "A"
    assert profile["current_level"]["badge_emoji"] == "🌱"


def test_get_profile_achievements(db):
    """名片包含成就"""
    user, child, level, cl = _setup(db)

    ach = Achievement(name="首次读完", type=Achievement.TYPE_BOOK_MILESTONE,
                      badge_emoji="📚")
    db.add(ach); db.commit()

    ca = ChildAchievement(child_id=child.id, achievement_id=ach.id)
    db.add(ca); db.commit()

    svc = ProfileService(db)
    profile = svc.get_profile(child.id)

    assert profile["achievement_count"] == 1
    assert len(profile["achievements"]) == 1
    assert profile["achievements"][0]["name"] == "首次读完"


def test_get_profile_nonexistent(db):
    """不存在的孩子返回None"""
    user, child, level, cl = _setup(db)
    svc = ProfileService(db)
    profile = svc.get_profile(99999)
    assert profile is None
