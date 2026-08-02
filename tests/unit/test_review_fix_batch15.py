# tests/unit/test_review_fix_batch15.py
"""批次15 审查返修单测 — P0-1 押金列类型 / P1-2 冷却时区 / P1-3 读完打卡 / P2-4 回调幂等

对应《K3决策批次落地审查报告-20260802.md》逐项修复。
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import DepositStatus, MemberStatus
from backend.database import Base
from backend.domain.book.models import Book
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord, FinePayment
from backend.domain.deposit.service import DepositService
from backend.domain.reading.models import CheckIn, ReadingProgress
from backend.domain.reading.service import ReadingService
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
    user = User(openid="b15", phone="13800001111")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="返修", age=7, grade="二年级", status=status)
    db.add(child)
    db.commit()
    return user, child


class TestP0PayOrderIdString:
    """P0-1：pay_order_id 存字符串单号 + 回调按字符串命中"""

    def test_deposit_record_stores_string_order_no(self, db):
        _, child = _mk_child(db)
        record = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200"),
            status=DepositStatus.PENDING,
            pay_order_id="DP" + "A" * 24,
        )
        db.add(record)
        db.commit()
        got = (
            db.query(DepositRecord)
            .filter(DepositRecord.pay_order_id == "DP" + "A" * 24)
            .first()
        )
        assert got is not None and got.id == record.id

    def test_callback_finds_by_string(self, db):
        _, child = _mk_child(db)
        record = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200"),
            status=DepositStatus.PENDING,
            pay_order_id="DP" + "B" * 24,
        )
        db.add(record)
        db.commit()
        svc = DepositService(db)
        result = svc.handle_callback("DP" + "B" * 24, Decimal("1200"))
        assert result.status == DepositStatus.PAID


class TestP1CooldownLocalTime:
    """P1-2：冷却比较使用本地时间（与 ORM func.now() 同口径）"""

    def test_recent_quiz_blocks_within_10min(self, db):
        from backend.domain.advancement.models import Quiz, QuestionBank
        from backend.domain.advancement.schemas import QuizStartRequest
        from backend.domain.advancement.service import AdvancementService
        from backend.common.exceptions import ConflictError
        from sqlalchemy import update

        _, child = _mk_child(db)
        book = Book(
            isbn="B15-Q",
            title="书",
            author="A",
            ar_value=Decimal("1.0"),
            age_min=3,
            age_max=9,
            word_count=100,
        )
        db.add(book)
        db.commit()
        db.add(
            QuestionBank(
                book_id=book.id,
                question_text="q?",
                option_a="A",
                option_b="B",
                correct_answer="A",
            )
        )
        quiz = Quiz(child_id=child.id, book_id=book.id, status=1, total_questions=3)
        db.add(quiz)
        db.commit()
        # create_time 用本地时间 5 分钟前（模拟 MySQL func.now() 口径）
        db.execute(
            update(Quiz)
            .where(Quiz.id == quiz.id)
            .values(create_time=datetime.now() - timedelta(minutes=5))
        )
        db.commit()

        svc = AdvancementService(db)
        with pytest.raises(ConflictError, match="冷却"):
            svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))

    def test_old_quiz_allows(self, db):
        from backend.domain.advancement.models import Quiz, QuestionBank
        from backend.domain.advancement.schemas import QuizStartRequest
        from backend.domain.advancement.service import AdvancementService
        from sqlalchemy import update

        _, child = _mk_child(db)
        book = Book(
            isbn="B15-Q2",
            title="书2",
            author="A",
            ar_value=Decimal("1.0"),
            age_min=3,
            age_max=9,
            word_count=100,
        )
        db.add(book)
        db.commit()
        db.add(
            QuestionBank(
                book_id=book.id,
                question_text="q?",
                option_a="A",
                option_b="B",
                correct_answer="A",
            )
        )
        quiz = Quiz(child_id=child.id, book_id=book.id, status=1, total_questions=3)
        db.add(quiz)
        db.commit()
        db.execute(
            update(Quiz)
            .where(Quiz.id == quiz.id)
            .values(create_time=datetime.now() - timedelta(hours=2))
        )
        db.commit()

        svc = AdvancementService(db)
        result = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
        assert result.id is not None


class TestP1FinishBookCheckin:
    """P1-3：读完触发 TYPE_FINISH_BOOK 打卡 + total_books_finished 累计（首次去重）"""

    def _finish_book(self, db, child, book_id, total_pages=10):
        svc = ReadingService(db)
        from backend.domain.reading.schemas import SaveProgressRequest

        return svc.save_progress(
            child.id,
            SaveProgressRequest(
                book_id=book_id, current_page=total_pages, total_pages=total_pages
            ),
        )

    def test_finish_creates_checkin_and_increments(self, db):
        _, child = _mk_child(db)
        book = Book(
            isbn="B15-F",
            title="书",
            author="A",
            ar_value=Decimal("1.0"),
            age_min=3,
            age_max=9,
            word_count=100,
        )
        db.add(book)
        db.commit()

        self._finish_book(db, child, book.id)
        checkin = (
            db.query(CheckIn)
            .filter(
                CheckIn.child_id == child.id,
                CheckIn.check_type == CheckIn.TYPE_FINISH_BOOK,
            )
            .first()
        )
        assert checkin is not None
        db.refresh(child)
        assert child.total_books_finished == 1

    def test_refinish_same_book_no_double_count(self, db):
        _, child = _mk_child(db)
        book = Book(
            isbn="B15-F2",
            title="书2",
            author="A",
            ar_value=Decimal("1.0"),
            age_min=3,
            age_max=9,
            word_count=100,
        )
        db.add(book)
        db.commit()

        self._finish_book(db, child, book.id)
        self._finish_book(db, child, book.id)  # 重读同一本
        db.refresh(child)
        assert child.total_books_finished == 1  # 不重复累计

    def test_two_books_same_day_one_checkin_two_books(self, db):
        """同一天读完 2 本：打卡每类型仅 1 次，但读完本数 = 2"""
        _, child = _mk_child(db)
        for i, isbn in enumerate(("B15-G1", "B15-G2")):
            db.add(
                Book(
                    isbn=isbn,
                    title=f"书{i}",
                    author="A",
                    ar_value=Decimal("1.0"),
                    age_min=3,
                    age_max=9,
                    word_count=100,
                )
            )
        db.commit()
        books = db.query(Book).all()
        for b in books:
            self._finish_book(db, child, b.id)

        db.refresh(child)
        assert child.total_books_finished == 2
        checkin_count = (
            db.query(CheckIn)
            .filter(
                CheckIn.child_id == child.id,
                CheckIn.check_type == CheckIn.TYPE_FINISH_BOOK,
                CheckIn.check_date == date.today(),
            )
            .count()
        )
        assert checkin_count == 1  # C1：每类型每日各 1 次

    def test_reconcile_uses_reading_progress(self, db):
        """对账口径：total_books_finished 以 reading_progress.is_finished 重算"""
        from backend.tasks.scheduler import reconcile_child_stats

        _, child = _mk_child(db)
        # 手工构造：progress 2 本读完，child 统计被污染为 0
        for i, isbn in enumerate(("B15-R1", "B15-R2")):
            book = Book(
                isbn=isbn,
                title=f"书{i}",
                author="A",
                ar_value=Decimal("1.0"),
                age_min=3,
                age_max=9,
                word_count=100,
            )
            db.add(book)
            db.commit()
            db.add(
                ReadingProgress(
                    child_id=child.id,
                    book_id=book.id,
                    current_page=10,
                    total_pages=10,
                    is_finished=1,
                )
            )
        db.commit()
        child.total_books_finished = 0
        db.commit()

        reconcile_child_stats(db)
        db.refresh(child)
        assert child.total_books_finished == 2


class TestP2FineCallbackIdempotent:
    """P2-4：FINE 单重复回调幂等成功"""

    def test_duplicate_callback_returns_true(self, db):
        _, child = _mk_child(db)
        child.outstanding_fines = Decimal("10")
        db.commit()
        record = FinePayment(
            child_id=child.id, amount=Decimal("10"), pay_order_no="FINE-DUP-1"
        )
        db.add(record)
        db.commit()

        svc = DepositService(db)
        assert svc.handle_fine_callback("FINE-DUP-1") is True  # 首次核销
        assert svc.handle_fine_callback("FINE-DUP-1") is True  # 重复回调幂等
        assert svc.handle_fine_callback("FINE-NOT-EXIST") is False  # 不存在走押金链路
