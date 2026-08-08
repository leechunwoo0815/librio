# tests/unit/test_reconcile_child_stats.py
"""reconcile_child_stats 统计字段对账 — 单元测试"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.advancement.models import Quiz
from backend.domain.book.models import Book
from backend.domain.child.models import Child
from backend.domain.reading.models import CheckIn, ReadingSession
from backend.domain.user.models import User
from backend.tasks import scheduler


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine, monkeypatch):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def _disable_locks(monkeypatch):
    import functools

    def _noop(*args, **kwargs):
        def deco(func):
            @functools.wraps(func)
            def wrapper(*a, **kw):
                return func(*a, **kw)

            return wrapper

        return deco

    monkeypatch.setattr(scheduler, "distributed_lock", _noop)


def _make_user(db):
    u = User(openid=f"test_openid_{uuid.uuid4().hex[:8]}", parent_name="测试家长")
    db.add(u)
    db.flush()
    db.refresh(u)
    return u


def _make_child(db, user, **stats):
    c = Child(user_id=user.id, name="测试孩子", age=5, grade="中班", **stats)
    db.add(c)
    db.flush()
    db.refresh(c)
    return c


def _make_book(db, word_count=1000):
    b = Book(
        title=f"测试书{uuid.uuid4().hex[:4]}",
        author="测试作者",
        isbn=uuid.uuid4().hex[:13],
        ar_value=3.0,
        age_min=3,
        age_max=8,
        word_count=word_count,
    )
    db.add(b)
    db.flush()
    db.refresh(b)
    return b


def _pass_quiz(db, child_id, book_id, score=90):
    q = Quiz(
        child_id=child_id,
        book_id=book_id,
        status=Quiz.STATUS_COMPLETED,
        score=Decimal(str(score)),
        total_questions=5,
        correct_count=4,
    )
    db.add(q)
    db.flush()
    return q


class TestReconcileChildStats:
    def test_consistent_no_change(self, db):
        user = _make_user(db)
        book = _make_book(db, word_count=500)
        child = _make_child(
            db,
            user,
            total_words_read=500,
            total_reading_minutes=0,
            total_books_finished=0,
            current_streak_days=0,
            longest_streak_days=0,
        )
        _pass_quiz(db, child.id, book.id)
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.total_words_read == 500

    def test_words_drift_fixed(self, db):
        """words 漂移：两本通过的书只计一次（同书重复通过不重复计）"""
        user = _make_user(db)
        b1 = _make_book(db, word_count=800)
        b2 = _make_book(db, word_count=1200)
        child = _make_child(db, user, total_words_read=99999)
        _pass_quiz(db, child.id, b1.id)
        _pass_quiz(db, child.id, b1.id)  # 同书重复通过
        _pass_quiz(db, child.id, b2.id)
        _pass_quiz(db, child.id, b2.id, score=50)  # 未通过不计
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.total_words_read == 2000

    def test_minutes_and_books_fixed(self, db):
        user = _make_user(db)
        child = _make_child(db, user, total_reading_minutes=0, total_books_finished=0)
        db.add(
            ReadingSession(
                child_id=child.id,
                book_id=1,
                start_time=datetime.now(),
                duration_seconds=1800,
            )
        )
        db.add(
            ReadingSession(
                child_id=child.id,
                book_id=2,
                start_time=datetime.now(),
                duration_seconds=900,
            )
        )
        # P1-3：对账口径改为 reading_progress.is_finished 计数
        from backend.domain.reading.models import ReadingProgress

        db.add(
            ReadingProgress(
                child_id=child.id,
                book_id=1,
                current_page=10,
                total_pages=10,
                is_finished=1,
            )
        )
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.total_reading_minutes == 45
        assert child.total_books_finished == 1

    def test_streak_current_and_longest(self, db):
        """streak：今天起连续 3 天；历史最长 5 天段"""
        user = _make_user(db)
        child = _make_child(db, user, current_streak_days=0, longest_streak_days=0)
        today = date.today()
        # 近 3 天连续
        for i in range(3):
            db.add(
                CheckIn(
                    child_id=child.id,
                    check_type=1,
                    check_date=datetime.combine(
                        today - timedelta(days=i), datetime.min.time()
                    ),
                )
            )
        # 上周 5 天连续（与近 3 天间隔 2 天）
        for i in range(7, 12):
            db.add(
                CheckIn(
                    child_id=child.id,
                    check_type=1,
                    check_date=datetime.combine(
                        today - timedelta(days=i), datetime.min.time()
                    ),
                )
            )
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.current_streak_days == 3
        assert child.longest_streak_days == 5

    def test_streak_broken_yesterday_gone(self, db):
        """昨天以前没打卡：current=0"""
        user = _make_user(db)
        child = _make_child(db, user, current_streak_days=7)
        db.add(
            CheckIn(
                child_id=child.id,
                check_type=1,
                check_date=datetime.now() - timedelta(days=5),
            )
        )
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.current_streak_days == 0
        # longest 只升不降：5 天前的单次打卡不影响 longest
        assert child.longest_streak_days == 1

    def test_longest_never_decreases(self, db):
        """longest 只升不降：库存最长 10 天，计算最长 2 天 → 保持 10"""
        user = _make_user(db)
        child = _make_child(db, user, longest_streak_days=10)
        today = date.today()
        for i in range(2):
            db.add(
                CheckIn(
                    child_id=child.id,
                    check_type=1,
                    check_date=datetime.combine(
                        today - timedelta(days=i), datetime.min.time()
                    ),
                )
            )
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.longest_streak_days == 10

    def test_incremental_window_skips_old_data(self, db):
        """F-036：非全量日只重算近 7 天数据——30 天前的漂移不参与当日对账"""
        user = _make_user(db)
        book = _make_book(db, word_count=800)
        child = _make_child(db, user, total_words_read=99999)
        q = _pass_quiz(db, child.id, book.id)
        # 把测验时间改成 30 天前（增量窗口外）
        q.create_time = datetime.now() - timedelta(days=30)
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        # 当月不是 1 号时（测试环境当前 8 月）：旧数据不进窗口，漂移保留
        if date.today().day != 1:
            assert child.total_words_read == 99999
        else:
            assert child.total_words_read == 800

    def test_incremental_window_covers_recent_data(self, db):
        """F-036：近 7 天数据参与增量对账"""
        user = _make_user(db)
        book = _make_book(db, word_count=800)
        child = _make_child(db, user, total_words_read=99999)
        _pass_quiz(db, child.id, book.id)  # create_time=now，窗口内
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.total_words_read == 800

    def test_incremental_only_fixes_aggregated_fields(self, db):
        """F-036 语义守护：窗口内只有 Quiz 的孩子——只修 words，
        不得把未聚合到的 minutes/books 历史值误清零"""
        user = _make_user(db)
        book = _make_book(db, word_count=800)
        child = _make_child(
            db,
            user,
            total_words_read=99999,
            total_reading_minutes=45,
            total_books_finished=2,
        )
        _pass_quiz(db, child.id, book.id)  # 窗口内 Quiz，无 minutes/books 记录
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.total_words_read == 800  # 本次聚合到的字段被修正
        assert child.total_reading_minutes == 45  # 未聚合字段保留历史值
        assert child.total_books_finished == 2

    def test_full_reconcile_first_day_of_month(self, db, monkeypatch):
        """F-036：每月 1 日全量——30 天前数据也参与对账"""
        import backend.tasks.scheduler as sched_mod

        real_date = sched_mod.date

        class _FakeDate(real_date):
            @classmethod
            def today(cls):
                return cls(2026, 8, 1)

        monkeypatch.setattr(sched_mod, "date", _FakeDate)
        user = _make_user(db)
        book = _make_book(db, word_count=800)
        child = _make_child(db, user, total_words_read=99999)
        q = _pass_quiz(db, child.id, book.id)
        q.create_time = datetime.now() - timedelta(days=30)
        db.commit()

        scheduler.reconcile_child_stats(db)
        db.refresh(child)
        assert child.total_words_read == 800
