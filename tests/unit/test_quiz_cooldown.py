"""测验冷却单元测试 — T3.4 quiz_cooldown_minutes 可配置"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.advancement.models import Quiz, QuestionBank
from backend.domain.book.models import Book
from backend.domain.advancement.service import AdvancementService
from backend.domain.advancement.schemas import QuizStartRequest
from backend.common.exceptions import ConflictError


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def advancement_service(db):
    return AdvancementService(db)


def _now_utc():
    """匹配 start_quiz 中的时间获取方式"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _setup_quiz(db, child_id, book_id, create_time, status=1):
    """创建一条已完成测验记录（create_time 手动覆盖 func.now() 默认值）"""
    quiz = Quiz(
        child_id=child_id,
        book_id=book_id,
        status=status,
        total_questions=5,
        correct_count=4,
        score=80.0,
    )
    db.add(quiz)
    db.commit()
    db.execute(
        update(Quiz).where(Quiz.id == quiz.id).values(create_time=create_time)
    )
    db.commit()
    db.refresh(quiz)
    return quiz


def _setup_question(db, book_id):
    q = QuestionBank(
        book_id=book_id,
        question_text="test?",
        option_a="A",
        option_b="B",
        option_c="C",
        option_d="D",
        correct_answer="A",
        difficulty=1,
    )
    db.add(q)
    db.commit()
    return q


class TestQuizCooldown:
    """start_quiz 冷却校验测试"""

    def test_cooldown_blocks_within_window(self, db, advancement_service):
        """冷却期内重考 → ConflictError"""
        user = User(openid="qc1", phone="1")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="测试", age=6, grade="一年级", status=1, deposit_status=1)
        db.add(child)
        db.commit()
        book = Book(title="测试书", isbn="T001", author="作者", word_count=100, ar_value=2.0, age_min=3, age_max=15)
        db.add(book)
        db.commit()
        _setup_question(db, book.id)
        _setup_quiz(db, child.id, book.id, _now_utc() - timedelta(minutes=5))

        data = QuizStartRequest(book_id=book.id)
        with pytest.raises(ConflictError, match="冷却"):
            advancement_service.start_quiz(child.id, data)

    def test_cooldown_allows_after_window(self, db, advancement_service):
        """冷却期外重考 → 正常返回"""
        user = User(openid="qc2", phone="2")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="测试", age=6, grade="一年级", status=1, deposit_status=1)
        db.add(child)
        db.commit()
        book = Book(title="测试书2", isbn="T002", author="作者", word_count=100, ar_value=2.0, age_min=3, age_max=15)
        db.add(book)
        db.commit()
        _setup_question(db, book.id)
        _setup_quiz(db, child.id, book.id, _now_utc() - timedelta(hours=2))

        data = QuizStartRequest(book_id=book.id)
        result = advancement_service.start_quiz(child.id, data)
        assert result is not None
        assert result.book_id == book.id

    def test_no_previous_quiz(self, db, advancement_service):
        """无历史测验 → 正常返回"""
        user = User(openid="qc3", phone="3")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="测试", age=6, grade="一年级", status=1, deposit_status=1)
        db.add(child)
        db.commit()
        book = Book(title="测试书3", isbn="T003", author="作者", word_count=100, ar_value=2.0, age_min=3, age_max=15)
        db.add(book)
        db.commit()
        _setup_question(db, book.id)

        data = QuizStartRequest(book_id=book.id)
        result = advancement_service.start_quiz(child.id, data)
        assert result is not None

    def test_different_book_no_block(self, db, advancement_service):
        """不同图书不触发冷却"""
        user = User(openid="qc4", phone="4")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="测试", age=6, grade="一年级", status=1, deposit_status=1)
        db.add(child)
        db.commit()
        book1 = Book(title="书A", isbn="T004", author="作者", word_count=100, ar_value=2.0, age_min=3, age_max=15)
        book2 = Book(title="书B", isbn="T005", author="作者", word_count=100, ar_value=2.0, age_min=3, age_max=15)
        db.add(book1)
        db.add(book2)
        db.commit()
        _setup_question(db, book1.id)
        _setup_question(db, book2.id)
        _setup_quiz(db, child.id, book1.id, _now_utc() - timedelta(minutes=5))

        data = QuizStartRequest(book_id=book2.id)
        result = advancement_service.start_quiz(child.id, data)
        assert result is not None
