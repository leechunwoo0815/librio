# tests/unit/test_fine_payment_low_quiz.py
"""批次13 后端单元测试 — B12 线上缴罚款 + C2 低龄测验规则"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.database import Base
from backend.common.exceptions import ValidationError
from backend.common.types import MemberStatus
from backend.domain.advancement.models import ChildLevel, Level, QuestionBank
from backend.domain.advancement.schemas import QuizStartRequest
from backend.domain.advancement.service import AdvancementService
from backend.domain.book.models import Book
from backend.domain.child.models import Child
from backend.domain.deposit.models import FinePayment
from backend.domain.deposit.schemas import DepositRefundRequest
from backend.domain.deposit.service import DepositService
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


def _mk(db):
    user = User(openid="fp9", phone="13800001001")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id, name="小明", age=5, grade="大班", status=MemberStatus.OFFICIAL
    )
    db.add(child)
    db.commit()
    return user, child


class TestPayFines:
    def test_pay_fines_settles_outstanding(self, db):
        """B12：缴罚款成功 → outstanding_fines 归零"""
        user, child = _mk(db)
        child.outstanding_fines = Decimal("36.50")
        db.commit()

        gateway = MagicMock()
        gateway.create_order = AsyncMock(
            return_value=MagicMock(success=True, pay_params={"prepay_id": "x"})
        )
        gateway.supports_instant_payment = True

        svc = DepositService(db)
        import asyncio

        result = asyncio.run(
            svc.pay_fines(DepositRefundRequest(child_id=child.id), gateway, user)
        )
        assert result["amount"] == "36.50"
        db.refresh(child)
        assert child.outstanding_fines == Decimal("0")

        record = db.query(FinePayment).filter_by(child_id=child.id).one()
        assert record.status == FinePayment.STATUS_PAID

    def test_pay_fines_no_outstanding_rejected(self, db):
        """无未缴罚款时不可发起"""
        user, child = _mk(db)
        svc = DepositService(db)
        import asyncio

        with pytest.raises(ValidationError, match="没有未缴罚款"):
            asyncio.run(
                svc.pay_fines(
                    DepositRefundRequest(child_id=child.id), MagicMock(), user
                )
            )

    def test_fine_callback_settles(self, db):
        """回调链路核销（生产微信回调场景）"""
        user, child = _mk(db)
        child.outstanding_fines = Decimal("10")
        db.commit()
        record = FinePayment(
            child_id=child.id,
            amount=Decimal("10"),
            pay_order_no="FINE-TEST-CB",
        )
        db.add(record)
        db.commit()

        svc = DepositService(db)
        assert svc.handle_fine_callback("FINE-TEST-CB") is True
        db.refresh(child)
        assert child.outstanding_fines == Decimal("0")
        # 重复回调幂等成功（P2-4：微信重试不再 500）
        assert svc.handle_fine_callback("FINE-TEST-CB") is True


class TestLowLevelQuiz:
    def _mk_low_child(self, db, sort_order=2):
        user, child = _mk(db)
        level = Level(name="B", sort_order=sort_order, required_books=3)
        db.add(level)
        db.commit()
        db.add(ChildLevel(child_id=child.id, level_id=level.id, is_current=True))
        book = Book(
            isbn="LQ1",
            title="低龄书",
            author="A",
            ar_value=Decimal("1.0"),
            age_min=3,
            age_max=6,
            word_count=100,
        )
        db.add(book)
        db.commit()
        for i in range(5):
            db.add(
                QuestionBank(
                    book_id=book.id,
                    question_text=f"Q{i}?",
                    option_a="A",
                    option_b="B",
                    correct_answer="A",
                )
            )
        db.commit()
        return child, book

    def test_low_level_quiz_3_questions(self, db):
        """C2：A-F 级出题 3 题（题库有 5 题只取 3）"""
        child, book = self._mk_low_child(db)
        svc = AdvancementService(db)
        quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
        assert quiz.total_questions == 3

    def test_low_level_pass_with_2_correct(self, db):
        """C2：3 题答对 2 题即通过（不再要求 80%）"""
        child, book = self._mk_low_child(db)
        svc = AdvancementService(db)
        quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
        questions = svc.question_repo.get_by_book(book.id)[:3]
        answers = [
            {"question_id": questions[0].id, "answer": "A"},  # 对
            {"question_id": questions[1].id, "answer": "A"},  # 对
            {"question_id": questions[2].id, "answer": "B"},  # 错
        ]
        result = svc.submit_answers(quiz.id, answers)
        assert result["passed"] is True
        assert result["correct_count"] == 2

    def test_low_level_fail_with_1_correct(self, db):
        child, book = self._mk_low_child(db)
        svc = AdvancementService(db)
        quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
        questions = svc.question_repo.get_by_book(book.id)[:3]
        answers = [
            {"question_id": questions[0].id, "answer": "A"},
            {"question_id": questions[1].id, "answer": "B"},
            {"question_id": questions[2].id, "answer": "B"},
        ]
        result = svc.submit_answers(quiz.id, answers)
        assert result["passed"] is False

    def test_high_level_keeps_global_rule(self, db):
        """高级别（sort_order>6）仍走 5 题 80%"""
        user, child = _mk(db)
        level = Level(name="Z", sort_order=26, required_books=5)
        db.add(level)
        db.commit()
        db.add(ChildLevel(child_id=child.id, level_id=level.id, is_current=True))
        book = Book(
            isbn="LQ2",
            title="高龄书",
            author="A",
            ar_value=Decimal("5.0"),
            age_min=10,
            age_max=15,
            word_count=5000,
        )
        db.add(book)
        db.commit()
        for i in range(6):
            db.add(
                QuestionBank(
                    book_id=book.id,
                    question_text=f"Q{i}?",
                    option_a="A",
                    option_b="B",
                    correct_answer="A",
                )
            )
        db.commit()
        svc = AdvancementService(db)
        quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
        assert quiz.total_questions == 5


class TestLeaderboardAgeGroup:
    """C6：排行榜年龄段分组（3-6/7-9/10-12/13-15）"""

    def test_total_leaderboard_filters_age_group(self, db):
        from backend.domain.advancement.leaderboard_service import LeaderboardService

        young = Child(
            user_id=1,
            name="小宝",
            age=5,
            grade="大班",
            status=2,
            total_words_read=9000,
            total_books_finished=9,
        )
        db.add(young)
        teen = Child(
            user_id=1,
            name="大宝",
            age=13,
            grade="初一",
            status=2,
            total_words_read=5000,
            total_books_finished=3,
        )
        db.add(teen)
        db.commit()

        svc = LeaderboardService(db)
        all_entries = svc.get_leaderboard(period="total")
        assert len(all_entries) == 2  # 不分组时全量

        young_entries = svc.get_leaderboard(period="total", age_group="3-6")
        assert len(young_entries) == 1
        assert young_entries[0]["display_name"].startswith("小宝")

        teen_entries = svc.get_leaderboard(period="total", age_group="13-15")
        assert len(teen_entries) == 1
        assert teen_entries[0]["display_name"].startswith("大宝")

    def test_invalid_age_group_ignored(self, db):
        from backend.domain.advancement.leaderboard_service import LeaderboardService

        svc = LeaderboardService(db)
        assert svc._parse_age_group("abc") is None
        assert svc._parse_age_group(None) is None
        assert svc._parse_age_group("3-6") == (3, 6)


class TestQuizPassCountPerLevel:
    """C6：测验通过数随级别 required_books 收敛（A-F 3 本 → 3 次）"""

    def test_min_quiz_pass_capped_by_required_books(self, db):
        from backend.common.config_service import ConfigService

        user, child = _mk(db)
        level = Level(name="A2", sort_order=1, required_books=3)
        db.add(level)
        db.commit()
        # 直接验证配置与级别的取小逻辑
        min_pass = min(
            ConfigService.get_int(db, "quiz_pass_count", 5), level.required_books
        )
        assert min_pass == 3
