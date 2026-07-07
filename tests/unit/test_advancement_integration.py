# tests/unit/test_advancement_integration.py
"""
[What] V3.0 晋级集成测试
[Why] TDD: 测验通过后自动积分+还书+晋级检测的完整链路
[How] 测试submit_answers串联后续动作
"""

import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.bookshelf.models import Bookshelf
from backend.domain.advancement.models import ReadingSubmission
from backend.domain.advancement.models import Level, ChildLevel, QuestionBank, Quiz, Achievement, ChildAchievement
from backend.domain.advancement.service import AdvancementService
from backend.bootstrap import register_event_handlers


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Seed system_config defaults needed by ConfigService
    from backend.domain.admin.models import SystemConfig
    for key, (value, config_type, desc) in SystemConfig.DEFAULTS.items():
        session.add(SystemConfig(config_key=key, config_value=value, config_type=config_type, description=desc))
    session.commit()
    register_event_handlers()
    yield session
    session.close()


def _setup(db):
    """创建完整测试数据"""
    user = User(openid="test_integration", phone="13800138001")
    db.add(user); db.commit()

    child = Child(user_id=user.id, name="小明", age=7, grade="二年级",
                  status=Child.STATUS_OFFICIAL, english_name="Tom",
                  total_words_read=0, total_books_finished=0)
    db.add(child); db.commit()

    book = Book(isbn="978001", title="TestBook", author="Author",
                ar_value=2.0, age_min=5, age_max=9, word_count=3200)
    db.add(book); db.commit()

    level1 = Level(name="A", sort_order=1, required_books=3,
                   required_quiz_pass_rate=Decimal("0.80"), max_borrow_count=20,
                   badge_emoji="🌱", require_teacher_review=False)
    level2 = Level(name="B", sort_order=2, required_books=5,
                   required_quiz_pass_rate=Decimal("0.80"), max_borrow_count=20,
                   badge_emoji="🌿", require_teacher_review=False)
    db.add_all([level1, level2]); db.commit()

    cl = ChildLevel(child_id=child.id, level_id=level1.id, is_current=True,
                    books_read_at_level=2, quizzes_passed_at_level=0)
    db.add(cl); db.commit()

    q1 = QuestionBank(book_id=book.id, question_text="Q1",
                       option_a="A", option_b="B", correct_answer="A")
    q2 = QuestionBank(book_id=book.id, question_text="Q2",
                       option_a="A", option_b="B", correct_answer="B")
    db.add_all([q1, q2]); db.commit()

    shelf = Bookshelf(child_id=child.id, book_id=book.id, status=Bookshelf.STATUS_BORROWING)
    db.add(shelf); db.commit()

    submission = ReadingSubmission(child_id=child.id, book_id=book.id,
                                   status=ReadingSubmission.STATUS_PENDING)
    db.add(submission); db.commit()

    quiz = Quiz(child_id=child.id, book_id=book.id, submission_id=submission.id,
                total_questions=2)
    db.add(quiz); db.commit()

    return user, child, book, level1, level2, cl, [q1, q2], shelf, submission, quiz


def test_quiz_pass_updates_word_count(db):
    """测验通过后更新单词积分"""
    user, child, book, level1, level2, cl, questions, shelf, submission, quiz = _setup(db)

    svc = AdvancementService(db)
    result = svc.submit_answers(quiz.id, [
        {"question_id": questions[0].id, "answer": "A"},
        {"question_id": questions[1].id, "answer": "B"},
    ])
    assert result["passed"] is True

    db.refresh(child)
    assert child.total_words_read == book.word_count


def test_quiz_pass_auto_returns_from_shelf(db):
    """测验通过后自动从书架移除"""
    user, child, book, level1, level2, cl, questions, shelf, submission, quiz = _setup(db)

    svc = AdvancementService(db)
    svc.submit_answers(quiz.id, [
        {"question_id": questions[0].id, "answer": "A"},
        {"question_id": questions[1].id, "answer": "B"},
    ])

    db.refresh(shelf)
    assert shelf.status == Bookshelf.STATUS_RETURNED


def test_quiz_pass_does_not_auto_approve_submission(db):
    """测验通过后不自动批准阅读提交（由老师手动审核）"""
    user, child, book, level1, level2, cl, questions, shelf, submission, quiz = _setup(db)

    svc = AdvancementService(db)
    svc.submit_answers(quiz.id, [
        {"question_id": questions[0].id, "answer": "A"},
        {"question_id": questions[1].id, "answer": "B"},
    ])

    db.refresh(submission)
    # P0-9: 测验通过不再自动批准提交，保持待审核状态
    assert submission.status == ReadingSubmission.STATUS_PENDING


def test_review_submission_checks_advancement(db):
    """老师审核通过阅读提交后自动晋级"""
    user, child, book, level1, level2, cl, questions, shelf, submission, quiz = _setup(db)
    # 设为只差1本书就能晋级，且已通过足够测验（默认 quiz_pass_count=5）
    cl.books_read_at_level = level1.required_books - 1
    cl.quizzes_passed_at_level = 5
    db.commit()

    # P0-9: 晋级由老师审核阅读提交触发，而非测验通过
    svc = AdvancementService(db)
    from types import SimpleNamespace
    review_data = SimpleNamespace(status=1, comment="通过")  # STATUS_APPROVED = 1
    svc.review_submission(submission.id, review_data)

    # 老师审核通过 → books_read +1 → 满足晋级条件 → 自动晋级
    from backend.domain.advancement.repository import ChildLevelRepository
    cl_repo = ChildLevelRepository(db)
    current = cl_repo.get_current(child.id)
    assert current is not None
    assert current.level_id == level2.id


def test_word_count_not_duplicated_on_requiz(db):
    """同一本书第2次读完测评通过不重复计分"""
    user, child, book, level1, level2, cl, questions, shelf, submission, quiz = _setup(db)

    svc = AdvancementService(db)
    svc.submit_answers(quiz.id, [
        {"question_id": questions[0].id, "answer": "A"},
        {"question_id": questions[1].id, "answer": "B"},
    ])
    db.refresh(child)
    words_after_first = child.total_words_read

    # 第2次通过同一本书
    quiz2 = Quiz(child_id=child.id, book_id=book.id, total_questions=2)
    db.add(quiz2); db.commit()
    svc.submit_answers(quiz2.id, [
        {"question_id": questions[0].id, "answer": "A"},
        {"question_id": questions[1].id, "answer": "B"},
    ])
    db.refresh(child)
    assert child.total_words_read == words_after_first  # 不重复计分
