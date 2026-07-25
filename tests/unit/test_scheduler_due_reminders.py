# tests/unit/test_scheduler_due_reminders.py
"""check_due_date_reminders 单元测试 — F2 补缺"""

from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base


@pytest.fixture
def _stub_db(monkeypatch):
    """替换 _get_db_session 返回 MagicMock"""
    from backend.tasks import scheduler

    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.close = MagicMock()
    monkeypatch.setattr(scheduler, "_get_db_session", lambda: db)
    return db


@pytest.fixture
def sqlite_session(monkeypatch):
    """返回真实 SQLite 内存会话，替换 _get_db_session"""
    from backend.tasks import scheduler
    from backend.domain.borrow.models import BorrowRecord
    from backend.domain.child.models import Child
    from backend.domain.book.models import Book
    from backend.domain.user.models import User

    # 确保模型在被 Base.metadata.create_all 前完成注册
    _ = BorrowRecord, Child, Book, User

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(scheduler, "_get_db_session", lambda: session)
    yield session
    session.close()


@pytest.fixture
def _disable_locks(monkeypatch):
    """禁用 distributed_lock 装饰器"""
    import functools
    from backend.tasks import scheduler

    def _noop_decorator(*args, **kwargs):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*a, **kw):
                return func(*a, **kw)

            return wrapper

        return decorator

    monkeypatch.setattr(scheduler, "distributed_lock", _noop_decorator)


@pytest.fixture
def _stub_config(monkeypatch):
    """stub ConfigService.get_int_list 返回默认提醒天数"""
    from backend.common import config_service

    def _fake_get_int_list(db, key, default):
        return default

    monkeypatch.setattr(
        config_service.ConfigService, "get_int_list", _fake_get_int_list
    )


def _make_borrow_record(record_id, child_id, book_id, due_date, user_id=1):
    """构造 BorrowRecord mock"""
    rec = MagicMock()
    rec.id = record_id
    rec.child_id = child_id
    rec.book_id = book_id
    rec.due_date = due_date
    rec.status = 1  # BORROWING
    rec.is_deleted = 0
    return rec


def _make_child(child_id, user_id, name="TestChild"):
    """构造 Child mock"""
    c = MagicMock()
    c.id = child_id
    c.user_id = user_id
    c.name = name
    c.is_deleted = 0
    return c


def _make_book(book_id, title="Test Book"):
    """构造 Book mock"""
    b = MagicMock()
    b.id = book_id
    b.title = title
    return b


class TestCheckDueDateReminders:
    """F2: check_due_date_reminders 测试覆盖"""

    def test_no_records_no_messages(self, _stub_db, _disable_locks, _stub_config):
        """无到期记录时不创建消息"""
        from backend.tasks import scheduler

        _stub_db.query.return_value.join.return_value.outerjoin.return_value.filter.return_value.all.return_value = []

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.check_due_date_reminders()
            mock_create.assert_not_called()

    def test_creates_messages_for_matching_days(
        self, _stub_db, _disable_locks, _stub_config
    ):
        """到期天数为 5/3/1/0 时创建对应消息"""
        from backend.tasks import scheduler

        today = date.today()
        # 构造 4 条记录，分别在 5/3/1/0 天后到期
        records = []
        for i, delta in enumerate([5, 3, 1, 0]):
            rec = _make_borrow_record(
                i + 1,
                child_id=10 + i,
                book_id=20 + i,
                due_date=datetime.combine(
                    today + timedelta(days=delta), datetime.min.time()
                ),
                user_id=100 + i,
            )
            child = _make_child(10 + i, user_id=100 + i)
            book = _make_book(20 + i, title=f"Book{i}")
            records.append((rec, child, book))

        _stub_db.query.return_value.join.return_value.outerjoin.return_value.filter.return_value.all.return_value = records

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.check_due_date_reminders()
            assert mock_create.call_count == 4
            # 检查每条消息的 title 和 msg_type（3=借阅通知）
            for call_args in mock_create.call_args_list:
                assert call_args.kwargs.get("title") == "借阅到期提醒"
                assert call_args.kwargs.get("msg_type") == 3

    def test_due_date_upper_bound_filter(
        self, sqlite_session, _disable_locks, _stub_config
    ):
        """确认查询使用上界过滤（max_remind_days），30天外的记录不被提醒"""
        from backend.tasks import scheduler
        from backend.domain.borrow.models import BorrowRecord
        from backend.domain.child.models import Child
        from backend.domain.book.models import Book
        from backend.common.types import BorrowStatus, MemberStatus
        from backend.domain.user.models import User

        today = date.today()

        user = User(
            id=100,
            phone="13800000001",
            parent_name="测试家长",
            openid="test_openid_100",
            status=User.STATUS_ACTIVE,
        )
        sqlite_session.add(user)

        child = Child(
            id=10,
            user_id=100,
            name="小明",
            age=6,
            grade="一年级",
            status=MemberStatus.OFFICIAL,
        )
        sqlite_session.add(child)

        book = Book(
            id=20,
            isbn="978-0000000001",
            title="测试书",
            author="作者",
            ar_value=1.0,
            age_min=3,
            age_max=12,
        )
        sqlite_session.add(book)

        rec1 = BorrowRecord(
            id=1,
            child_id=10,
            book_id=20,
            borrow_time=datetime.now(),
            due_date=datetime.combine(today + timedelta(days=3), datetime.min.time()),
            status=BorrowStatus.BORROWING,
        )
        sqlite_session.add(rec1)

        rec2 = BorrowRecord(
            id=2,
            child_id=10,
            book_id=20,
            borrow_time=datetime.now(),
            due_date=datetime.combine(today + timedelta(days=30), datetime.min.time()),
            status=BorrowStatus.BORROWING,
        )
        sqlite_session.add(rec2)
        sqlite_session.commit()

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.check_due_date_reminders()
            assert mock_create.call_count == 1

    def test_zero_day_message_content(self, _stub_db, _disable_locks, _stub_config):
        """当天到期（days=0）的消息内容包含 '今天到期'"""
        from backend.tasks import scheduler

        today = date.today()
        rec = _make_borrow_record(
            1,
            child_id=10,
            book_id=20,
            due_date=datetime.combine(today, datetime.min.time()),
        )
        child = _make_child(10, user_id=100, name="小明")
        book = _make_book(20, title="测试书")
        _stub_db.query.return_value.join.return_value.outerjoin.return_value.filter.return_value.all.return_value = [
            (rec, child, book)
        ]

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.check_due_date_reminders()
            call = mock_create.call_args
            assert "今天到期" in call.kwargs["content"]
            assert "测试书" in call.kwargs["content"]

    def test_one_day_message_content(self, _stub_db, _disable_locks, _stub_config):
        """1 天后到期（days=1）的消息内容包含 '明天到期'"""
        from backend.tasks import scheduler

        today = date.today()
        rec = _make_borrow_record(
            1,
            child_id=10,
            book_id=20,
            due_date=datetime.combine(today + timedelta(days=1), datetime.min.time()),
        )
        child = _make_child(10, user_id=100)
        book = _make_book(20, title="明日书")
        _stub_db.query.return_value.join.return_value.outerjoin.return_value.filter.return_value.all.return_value = [
            (rec, child, book)
        ]

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.check_due_date_reminders()
            call = mock_create.call_args
            assert "明天到期" in call.kwargs["content"]

    def test_missing_child_skipped(self, _stub_db, _disable_locks, _stub_config):
        """child 为 None 时跳过"""
        from backend.tasks import scheduler

        today = date.today()
        rec = _make_borrow_record(
            1,
            child_id=10,
            book_id=20,
            due_date=datetime.combine(today, datetime.min.time()),
        )
        _stub_db.query.return_value.join.return_value.outerjoin.return_value.filter.return_value.all.return_value = [
            (rec, None, None)
        ]

        with patch.object(scheduler, "_create_message") as mock_create:
            scheduler.check_due_date_reminders()
            mock_create.assert_not_called()

    def test_exception_rolls_back(self, _stub_db, _disable_locks, _stub_config):
        """异常时回滚"""
        from backend.tasks import scheduler

        _stub_db.query.side_effect = RuntimeError("DB down")

        scheduler.check_due_date_reminders()
        _stub_db.rollback.assert_called_once()
        _stub_db.close.assert_called_once()
