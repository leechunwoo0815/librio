# tests/unit/test_advancement_service.py
"""
V3.1 晋级体系服务单元测试
验证级别管理、测验、晋级检测、成就业务逻辑
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.advancement.models import Level, ChildLevel, QuestionBank, Achievement
from backend.domain.advancement.service import AdvancementService
from backend.domain.quiz_question.models import QuizQuestion  # noqa: F401


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
    yield session
    session.close()


def _create_test_data(db):
    """创建测试数据"""
    user = User(openid="test_adv_user", phone="13800138001")
    db.add(user)
    db.commit()

    child = Child(user_id=user.id, name="小明", age=7, grade="二年级", status=Child.STATUS_OFFICIAL)
    db.add(child)
    db.commit()

    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=3.2, age_min=7, age_max=9, word_count=3200)
    db.add(book)
    db.commit()

    level1 = Level(name="阅读新手", badge_emoji="🌱", sort_order=1,
                   required_books=3, required_quiz_pass_rate=Decimal("0.80"),
                   max_borrow_count=1, max_ar_level=Decimal("2.0"),
                   require_teacher_review=False)
    level2 = Level(name="阅读达人", badge_emoji="🌿", sort_order=2,
                   required_books=5, required_quiz_pass_rate=Decimal("0.80"),
                   max_borrow_count=2, max_ar_level=Decimal("3.5"),
                   require_teacher_review=False)
    level3 = Level(name="阅读高手", badge_emoji="🌳", sort_order=3,
                   required_books=8, required_quiz_pass_rate=Decimal("0.80"),
                   max_borrow_count=3, max_ar_level=Decimal("5.0"),
                   require_teacher_review=False)
    db.add_all([level1, level2, level3])
    db.commit()

    return user, child, book, level1, level2, level3


# ==================== Level Tests ====================

def test_get_levels(db):
    """获取所有级别"""
    _create_test_data(db)
    svc = AdvancementService(db)
    levels = svc.get_levels()
    assert len(levels) == 3
    assert levels[0].sort_order < levels[1].sort_order


def test_get_current_level(db):
    """获取孩子当前级别"""
    _, child, _, level1, _, _ = _create_test_data(db)
    cl = ChildLevel(child_id=child.id, level_id=level1.id, is_current=True)
    db.add(cl)
    db.commit()

    svc = AdvancementService(db)
    result = svc.get_current_level(child.id)
    assert result is not None
    assert result.level_name == "阅读新手"


def test_get_current_level_not_assigned(db):
    """未分配级别返回 None"""
    _, child, _, _, _, _ = _create_test_data(db)
    svc = AdvancementService(db)
    result = svc.get_current_level(child.id)
    assert result is None


# ==================== Quiz Tests ====================

def test_start_quiz(db):
    """开始测验"""
    _, child, book, _, _, _ = _create_test_data(db)
    q1 = QuestionBank(book_id=book.id, question_text="Q1",
                       option_a="A", option_b="B", correct_answer="A")
    db.add(q1)
    db.commit()

    from backend.domain.advancement.schemas import QuizStartRequest
    svc = AdvancementService(db)
    quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
    assert quiz.id is not None
    assert quiz.total_questions == 1


def test_submit_answers_all_correct(db):
    """答题全部正确"""
    _, child, book, _, _, _ = _create_test_data(db)
    cl = ChildLevel(child_id=child.id, level_id=1, is_current=True)
    db.add(cl)
    db.commit()

    q1 = QuestionBank(book_id=book.id, question_text="Q1",
                       option_a="A", option_b="B", correct_answer="A")
    q2 = QuestionBank(book_id=book.id, question_text="Q2",
                       option_a="A", option_b="B", correct_answer="B")
    db.add_all([q1, q2])
    db.commit()

    from backend.domain.advancement.schemas import QuizStartRequest
    svc = AdvancementService(db)
    quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))

    result = svc.submit_answers(quiz.id, [
        {"question_id": q1.id, "answer": "A"},
        {"question_id": q2.id, "answer": "B"},
    ])
    assert result["correct"] == 2
    assert result["score"] == 100.0
    assert result["passed"] is True


def test_submit_answers_partial(db):
    """答题部分正确"""
    _, child, book, _, _, _ = _create_test_data(db)
    cl = ChildLevel(child_id=child.id, level_id=1, is_current=True)
    db.add(cl)
    db.commit()

    q1 = QuestionBank(book_id=book.id, question_text="Q1",
                       option_a="A", option_b="B", correct_answer="A")
    q2 = QuestionBank(book_id=book.id, question_text="Q2",
                       option_a="A", option_b="B", correct_answer="B")
    db.add_all([q1, q2])
    db.commit()

    from backend.domain.advancement.schemas import QuizStartRequest
    svc = AdvancementService(db)
    quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))

    result = svc.submit_answers(quiz.id, [
        {"question_id": q1.id, "answer": "A"},
        {"question_id": q2.id, "answer": "A"},  # wrong
    ])
    assert result["correct"] == 1
    assert result["score"] == 50.0
    assert result["passed"] is False


def test_submit_answers_already_completed(db):
    """测验已提交不允许重复提交"""
    _, child, book, _, _, _ = _create_test_data(db)
    q1 = QuestionBank(book_id=book.id, question_text="Q1",
                       option_a="A", option_b="B", correct_answer="A")
    db.add(q1)
    db.commit()

    from backend.domain.advancement.schemas import QuizStartRequest
    svc = AdvancementService(db)
    quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
    svc.submit_answers(quiz.id, [{"question_id": q1.id, "answer": "A"}])

    with pytest.raises(Exception, match="已"):
        svc.submit_answers(quiz.id, [{"question_id": q1.id, "answer": "A"}])


def test_get_quiz_questions(db):
    """获取题目返回正确答案（前端自行剥离用于 WXML 渲染）"""
    _, child, book, _, _, _ = _create_test_data(db)
    q1 = QuestionBank(book_id=book.id, question_text="Q1",
                       option_a="A", option_b="B", correct_answer="A")
    db.add(q1)
    db.commit()

    from backend.domain.advancement.schemas import QuizStartRequest
    svc = AdvancementService(db)
    quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
    questions = svc.get_quiz_questions(quiz.id, is_quiz_id=True)
    assert len(questions) == 1
    assert questions[0].get("correct_answer") == "A"


# ==================== Advancement Tests ====================

def test_check_and_advance_not_ready(db):
    """检查晋级条件 — 未满足"""
    _, child, _, level1, _, _ = _create_test_data(db)
    cl = ChildLevel(child_id=child.id, level_id=level1.id, is_current=True,
                    books_read_at_level=0, quizzes_passed_at_level=0)
    db.add(cl)
    db.commit()

    svc = AdvancementService(db)
    result = svc.check_and_advance(child.id)
    assert result is None


def test_check_and_advance_ready(db):
    """检查晋级条件 — 已满足，自动晋级"""
    _, child, _, level1, level2, _ = _create_test_data(db)
    cl = ChildLevel(child_id=child.id, level_id=level1.id, is_current=True,
                    books_read_at_level=level1.required_books, quizzes_passed_at_level=5)
    db.add(cl)
    db.commit()

    svc = AdvancementService(db)
    result = svc.check_and_advance(child.id)
    assert result is not None
    assert result.level_id == level2.id


def test_increment_books_read(db):
    """增加读完书数"""
    _, child, _, level1, _, _ = _create_test_data(db)
    cl = ChildLevel(child_id=child.id, level_id=level1.id, is_current=True,
                    books_read_at_level=0)
    db.add(cl)
    db.commit()

    svc = AdvancementService(db)
    svc.increment_books_read(child.id)
    db.refresh(cl)
    assert cl.books_read_at_level == 1


def test_increment_quizzes_passed(db):
    """增加测验通过数"""
    _, child, _, level1, _, _ = _create_test_data(db)
    cl = ChildLevel(child_id=child.id, level_id=level1.id, is_current=True,
                    quizzes_passed_at_level=0)
    db.add(cl)
    db.commit()

    svc = AdvancementService(db)
    svc.increment_quizzes_passed(child.id)
    db.refresh(cl)
    assert cl.quizzes_passed_at_level == 1


# ==================== Achievement Tests ====================

def test_grant_achievement(db):
    """授予成就"""
    _, child, _, _, _, _ = _create_test_data(db)
    ach = Achievement(name="首次晋级", description="完成第一次晋级", type=Achievement.TYPE_LEVEL_UP,
                      badge_emoji="⭐")
    db.add(ach)
    db.commit()

    svc = AdvancementService(db)
    result = svc.grant_achievement(child.id, ach.id)
    assert result["already_granted"] is False


def test_grant_achievement_duplicate(db):
    """重复授予"""
    _, child, _, _, _, _ = _create_test_data(db)
    ach = Achievement(name="首次晋级", type=Achievement.TYPE_LEVEL_UP, badge_emoji="⭐")
    db.add(ach)
    db.commit()

    svc = AdvancementService(db)
    svc.grant_achievement(child.id, ach.id)
    result = svc.grant_achievement(child.id, ach.id)
    assert result["already_granted"] is True


def test_get_child_achievements(db):
    """获取孩子成就列表"""
    _, child, _, _, _, _ = _create_test_data(db)
    ach1 = Achievement(name="首次晋级", type=Achievement.TYPE_LEVEL_UP, badge_emoji="⭐")
    ach2 = Achievement(name="读完10本", type=Achievement.TYPE_BOOK_MILESTONE, badge_emoji="📚")
    db.add_all([ach1, ach2])
    db.commit()

    svc = AdvancementService(db)
    svc.grant_achievement(child.id, ach1.id)
    svc.grant_achievement(child.id, ach2.id)

    achievements = svc.get_child_achievements(child.id)
    assert len(achievements) == 2
