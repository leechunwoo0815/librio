# tests/unit/test_leaderboard.py
"""
[What] 排行榜服务测试
[Why] 验证按时间维度的积分排名
[How] 测试7天/15天/月/总排行榜
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.advancement.models import Level, ChildLevel, ReadingSubmission
from backend.domain.advancement.leaderboard_service import LeaderboardService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup(db):
    """创建2个孩子，各有不同的阅读量"""
    user = User(openid="lb_user", phone="13800138002")
    db.add(user); db.commit()

    child1 = Child(user_id=user.id, name="小明", age=7, grade="二年级",
                   english_name="Tom", total_words_read=5000,
                   total_books_finished=2, current_streak_days=10)
    child2 = Child(user_id=user.id, name="小红", age=5, grade="幼儿园大班",
                   english_name="Lucy", total_words_read=8000,
                   total_books_finished=3, current_streak_days=5)
    db.add_all([child1, child2]); db.commit()

    level = Level(name="A", sort_order=1, required_books=10, max_borrow_count=20)
    db.add(level); db.commit()

    cl1 = ChildLevel(child_id=child1.id, level_id=level.id, is_current=True)
    cl2 = ChildLevel(child_id=child2.id, level_id=level.id, is_current=True)
    db.add_all([cl1, cl2]); db.commit()

    book1 = Book(isbn="978001", title="Book1", author="A", ar_value=2.0,
                 age_min=5, age_max=9, word_count=3000)
    book2 = Book(isbn="978002", title="Book2", author="B", ar_value=3.0,
                 age_min=5, age_max=9, word_count=5000)
    db.add_all([book1, book2]); db.commit()

    return user, child1, child2, book1, book2


def test_total_leaderboard(db):
    """总排行榜按累计积分排序"""
    user, child1, child2, book1, book2 = _setup(db)
    svc = LeaderboardService(db)
    board = svc.get_leaderboard(period="total", limit=10)
    assert len(board) == 2
    # 小红8000 > 小明5000
    assert board[0]["child_id"] == child2.id
    assert board[0]["total_words"] == 8000
    assert board[1]["child_id"] == child1.id
    assert board[1]["total_words"] == 5000


def test_leaderboard_medals(db):
    """前3名显示金银铜牌"""
    user, child1, child2, book1, book2 = _setup(db)
    # 添加第3个孩子
    child3 = Child(user_id=user.id, name="小华", age=8, grade="三年级",
                   english_name="Mike", total_words_read=2000)
    db.add(child3); db.commit()
    svc = LeaderboardService(db)
    board = svc.get_leaderboard(period="total", limit=10)
    assert board[0]["medal"] == "🥇"
    assert board[1]["medal"] == "🥈"
    assert board[2]["medal"] == "🥉"


def test_leaderboard_name_format(db):
    """排行榜姓名格式：拼音+英文名"""
    user, child1, child2, book1, book2 = _setup(db)
    svc = LeaderboardService(db)
    board = svc.get_leaderboard(period="total", limit=10)
    # 姓名格式: "xiaoming tom"
    for entry in board:
        assert " " in entry["display_name"]


def test_weekly_leaderboard(db):
    """7天排行榜只统计最近7天"""
    user, child1, child2, book1, book2 = _setup(db)

    # 小明最近7天读了1本
    sub1 = ReadingSubmission(
        child_id=child1.id, book_id=book1.id,
        status=ReadingSubmission.STATUS_APPROVED,
        submitted_at=datetime.now() - timedelta(days=2),
        word_count=book1.word_count,
    )
    # 小红10天前读的（不在7天内）
    sub2 = ReadingSubmission(
        child_id=child2.id, book_id=book2.id,
        status=ReadingSubmission.STATUS_APPROVED,
        submitted_at=datetime.now() - timedelta(days=10),
        word_count=book2.word_count,
    )
    db.add_all([sub1, sub2]); db.commit()

    svc = LeaderboardService(db)
    board = svc.get_leaderboard(period="7d", limit=10)
    # 7天内只有小明的3000词
    assert len(board) == 1
    assert board[0]["total_words"] == book1.word_count
