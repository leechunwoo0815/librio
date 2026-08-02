# tests/unit/test_review_fix_20260803.py
"""超级大审查(20260803) 返修单测 — 逐项可执行回归

对应《专家意见/超级大审查_20260803.md》：
P0-1 CheckIn 唯一约束兜底 / P0-3 罚款清零行锁 / P1-2 total_revenue Decimal /
P1-3 Redis 降级策略 / P1-4 LIKE 通配符转义 / P2-1 msg_sec_check suggest /
P2-2 pass_score Decimal 边界 / P2-3 access_token Redis 共享缓存
"""

import asyncio
from datetime import date
from decimal import Decimal

import pytest
import redis as redis_lib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.sql_utils import add_with_unique_fallback, escape_like
from backend.common.types import MemberStatus
from backend.database import Base
from backend.domain.book.models import Book
from backend.domain.child.models import Child
from backend.domain.reading.models import CheckIn
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


def _mk_child(db, status=MemberStatus.OFFICIAL):
    user = User(openid="rev0803", phone="13800002222")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="审查", age=7, grade="二年级", status=status)
    db.add(child)
    db.commit()
    return user, child


def _mk_book(db, book_id=1, title="测试书", word_count=100):
    book = Book(
        id=book_id,
        isbn=f"978-{book_id:013d}",
        title=title,
        author="Test",
        ar_value=1.0,
        age_min=3,
        age_max=12,
        total_stock=5,
        available_stock=5,
        word_count=word_count,
    )
    db.add(book)
    db.commit()
    return book


# ---------------------------------------------------------------- P0-1
class TestP01CheckInUnique:
    """CheckIn(child_id, check_date, check_type) 唯一约束 + 并发兜底"""

    def test_model_has_unique_constraint(self):
        from sqlalchemy import UniqueConstraint

        constraints = [
            c for c in CheckIn.__table_args__ if isinstance(c, UniqueConstraint)
        ]
        assert len(constraints) == 1
        assert constraints[0].name == "uq_checkin_child_date_type"

    def test_duplicate_insert_silently_skipped(self, db):
        """同 child+date+type 第二次插入返回 False 且不污染外层事务"""
        _, child = _mk_child(db)
        today = date.today()
        c1 = CheckIn(
            child_id=child.id, check_date=today, check_type=CheckIn.TYPE_READING
        )
        assert add_with_unique_fallback(db, c1) is True
        c2 = CheckIn(
            child_id=child.id, check_date=today, check_type=CheckIn.TYPE_READING
        )
        assert add_with_unique_fallback(db, c2) is False
        # 会话未被 IntegrityError 污染，可继续正常使用
        c3 = CheckIn(child_id=child.id, check_date=today, check_type=CheckIn.TYPE_VOICE)
        assert add_with_unique_fallback(db, c3) is True
        db.commit()
        count = (
            db.query(CheckIn)
            .filter(CheckIn.child_id == child.id, CheckIn.check_date == today)
            .count()
        )
        assert count == 2  # READING + VOICE，重复的 READING 被跳过

    def test_different_type_same_day_allowed(self, db):
        _, child = _mk_child(db)
        today = date.today()
        for t in (
            CheckIn.TYPE_READING,
            CheckIn.TYPE_FINISH_BOOK,
            CheckIn.TYPE_VOICE,
            CheckIn.TYPE_VOCABULARY,
        ):
            assert (
                add_with_unique_fallback(
                    db, CheckIn(child_id=child.id, check_date=today, check_type=t)
                )
                is True
            )
        db.commit()


# ---------------------------------------------------------------- P0-3
class TestP03ClearChildFines:
    def test_clear_child_fines_zeroes_amount(self, db):
        from backend.domain.admin.services.borrow_service import AdminBorrowService

        _, child = _mk_child(db)
        child.outstanding_fines = Decimal("50.00")
        db.commit()
        svc = AdminBorrowService(db)
        result = svc.clear_child_fines(child.id, admin_id=1)
        assert result["success"] is True
        assert result["cleared_amount"] == "50.00"
        db.refresh(child)
        assert child.outstanding_fines == 0


# ---------------------------------------------------------------- P1-2
class TestP12TotalRevenueDecimal:
    def test_total_revenue_not_float(self):
        from backend.domain.admin.admin_schemas import AdminDashboardResponse

        resp = AdminDashboardResponse(total_revenue=Decimal("1234.56"))
        assert isinstance(resp.total_revenue, Decimal)
        assert resp.total_revenue == Decimal("1234.56")

    def test_total_revenue_default(self):
        from backend.domain.admin.admin_schemas import AdminDashboardResponse

        assert AdminDashboardResponse().total_revenue == Decimal("0")


# ---------------------------------------------------------------- P1-3
class TestP13RedisDegrade:
    """Redis 宕机降级：fail_open 可配置 + TimeoutError 也被捕获"""

    class _BrokenRedis:
        def set(self, *a, **kw):
            raise redis_lib.TimeoutError("connection timeout")

    def _patch_broken(self, monkeypatch):
        monkeypatch.setattr(
            "backend.common.distributed_lock.get_redis_client",
            lambda: self._BrokenRedis(),
        )

    def test_fail_open_true_executes(self, monkeypatch):
        from backend.common.distributed_lock import redis_lock
        from backend.config import get_settings

        self._patch_broken(monkeypatch)
        monkeypatch.setattr(get_settings(), "REDIS_LOCK_FAIL_OPEN", True)
        with redis_lock("job:test_fail_open") as acquired:
            assert acquired is True

    def test_fail_open_false_skips(self, monkeypatch):
        from backend.common.distributed_lock import redis_lock
        from backend.config import get_settings

        self._patch_broken(monkeypatch)
        monkeypatch.setattr(get_settings(), "REDIS_LOCK_FAIL_OPEN", False)
        with redis_lock("job:test_fail_closed") as acquired:
            assert acquired is False

    def test_timeout_error_caught_not_just_connection_error(self, monkeypatch):
        """TimeoutError 是 RedisError 子类但不是 ConnectionError 子类——
        旧代码只捕 ConnectionError 会让异常直接炸出"""
        from backend.common.distributed_lock import redis_lock

        self._patch_broken(monkeypatch)
        try:
            with redis_lock("job:test_timeout") as acquired:
                assert acquired in (True, False)  # 不抛异常即通过
        except redis_lib.TimeoutError:
            pytest.fail("TimeoutError 未被捕获")


# ---------------------------------------------------------------- P1-4
class TestP14LikeEscape:
    def test_escape_like_wildcards(self):
        assert escape_like("100%") == "100\\%"
        assert escape_like("a_b") == "a\\_b"
        assert escape_like("50%_off\\") == "50\\%\\_off\\\\"
        assert escape_like("normal") == "normal"

    def test_book_search_literal_percent(self, db):
        """搜索 '100%' 只命中字面量，不匹配所有含 100 的书"""
        from backend.domain.book.repository import BookRepository

        _mk_book(db, book_id=901, title="100% 英文绘本")
        _mk_book(db, book_id=902, title="1000 stories")
        repo = BookRepository(db)
        items, total = repo.search(keyword="100%")
        assert total == 1
        assert items[0].title == "100% 英文绘本"

    def test_book_search_underscore_literal(self, db):
        from backend.domain.book.repository import BookRepository

        _mk_book(db, book_id=903, title="a_b 测试")
        _mk_book(db, book_id=904, title="axb 测试")
        repo = BookRepository(db)
        items, total = repo.search(keyword="a_b")
        assert total == 1
        assert items[0].title == "a_b 测试"


# ---------------------------------------------------------------- P2-1
class TestP21MsgSecCheckSuggest:
    """v2 接口 errcode=0 不代表通过，必须检查 result.suggest"""

    def _run_check(self, monkeypatch, wechat_resp: dict):
        from backend.domain.security import router as sec_router

        class _Resp:
            def json(self):
                return wechat_resp

        class _FakeAsyncClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **kw):
                return _Resp()

        class _FakeWechat:
            def get_access_token(self):
                return "fake_token"

        monkeypatch.setattr(sec_router.httpx, "AsyncClient", _FakeAsyncClient)
        req = sec_router.CheckTextRequest(content="测试内容")
        return asyncio.run(
            sec_router.check_text(req, wechat_service=_FakeWechat(), current_user=None)
        )

    def test_suggest_risky_rejected(self, monkeypatch):
        resp = self._run_check(
            monkeypatch,
            {
                "errcode": 0,
                "result": {"suggest": "risky", "label": 20001},
                "detail": [],
            },
        )
        assert resp.passed is False

    def test_suggest_review_rejected(self, monkeypatch):
        resp = self._run_check(
            monkeypatch,
            {
                "errcode": 0,
                "result": {"suggest": "review", "label": 20001},
                "detail": [],
            },
        )
        assert resp.passed is False

    def test_suggest_pass_allowed(self, monkeypatch):
        resp = self._run_check(
            monkeypatch,
            {"errcode": 0, "result": {"suggest": "pass", "label": 100}, "detail": []},
        )
        assert resp.passed is True

    def test_detail_risky_rejected(self, monkeypatch):
        resp = self._run_check(
            monkeypatch,
            {
                "errcode": 0,
                "result": {"suggest": "pass", "label": 100},
                "detail": [{"strategy": "keyword", "suggest": "risky", "errcode": 0}],
            },
        )
        assert resp.passed is False


# ---------------------------------------------------------------- P2-2
class TestP22PassScoreDecimal:
    def test_boundary_score_counts_in_reconcile(self, db):
        """score=80.00 恰好等于阈值 0.80×100 时必须算通过——
        旧代码 float(0.80)*100=80.00000000000001 会把 80.00 误判为不通过"""
        from backend.domain.advancement.models import Quiz
        from backend.tasks.scheduler import reconcile_child_stats

        _, child = _mk_child(db)
        book = _mk_book(db, book_id=910, word_count=100)
        quiz = Quiz(
            child_id=child.id,
            book_id=book.id,
            status=Quiz.STATUS_COMPLETED,
            score=Decimal("80.00"),
        )
        db.add(quiz)
        db.commit()

        reconcile_child_stats(db)
        db.refresh(child)
        assert child.total_words_read == 100


# ---------------------------------------------------------------- P2-3
class TestP23AccessTokenRedisCache:
    class _FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, key):
            return self.store.get(key)

        def set(self, key, value, ex=None):
            self.store[key] = value

    class _DownRedis:
        def get(self, key):
            raise redis_lib.ConnectionError("down")

        def set(self, *a, **kw):
            raise redis_lib.ConnectionError("down")

    def test_cross_instance_sharing_via_redis(self, monkeypatch):
        """实例 A set 后，新实例 B（内存为空）能从 Redis 读到——多进程共享"""
        from backend.domain.wechat.service import _AccessTokenCache

        fake = self._FakeRedis()
        monkeypatch.setattr(
            "backend.common.distributed_lock.get_redis_client", lambda: fake
        )
        a = _AccessTokenCache()
        a.set("tok_shared", 7200)
        assert _AccessTokenCache.REDIS_KEY in fake.store

        b = _AccessTokenCache()  # 模拟另一个进程（内存缓存为空）
        assert b.get() == "tok_shared"

    def test_redis_down_falls_back_to_memory(self, monkeypatch):
        from backend.domain.wechat.service import _AccessTokenCache

        monkeypatch.setattr(
            "backend.common.distributed_lock.get_redis_client",
            lambda: self._DownRedis(),
        )
        c = _AccessTokenCache()
        c.set("tok_local", 7200)  # Redis 写失败不抛异常
        assert c.get() == "tok_local"  # 内存兜底

    def test_redis_down_empty_memory_returns_none(self, monkeypatch):
        from backend.domain.wechat.service import _AccessTokenCache

        monkeypatch.setattr(
            "backend.common.distributed_lock.get_redis_client",
            lambda: self._DownRedis(),
        )
        assert _AccessTokenCache().get() is None
