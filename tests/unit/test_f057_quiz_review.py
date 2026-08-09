"""
F-057 终审闭环：取题不泄露答案；提交响应携带每题回顾（服务端权威判分）。

背景：后端剥离 correct_answer/explanation 后，前端不得再依赖取题接口本地判分。
判分与错题回顾一律以 submit 响应（question_review）为准。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.advancement.models import QuestionBank
from backend.domain.advancement.service import AdvancementService
from backend.domain.advancement.schemas import QuizStartRequest


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    from backend.domain.admin.models import SystemConfig

    for key, (value, config_type, desc) in SystemConfig.DEFAULTS.items():
        session.add(
            SystemConfig(
                config_key=key,
                config_value=value,
                config_type=config_type,
                description=desc,
            )
        )
    session.commit()
    yield session
    session.close()


def _seed(db):
    user = User(openid="f057_openid", phone="13800138057")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F057",
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
    )
    db.add(child)
    db.commit()
    book = Book(
        isbn="9780064400570",
        title="F057 Book",
        author="F",
        ar_value=3.0,
        age_min=7,
        age_max=9,
        word_count=100,
    )
    db.add(book)
    db.commit()
    q1 = QuestionBank(
        book_id=book.id,
        question_text="Q1",
        option_a="AA",
        option_b="BB",
        correct_answer="A",
        explanation="解析一",
    )
    q2 = QuestionBank(
        book_id=book.id,
        question_text="Q2",
        option_a="AA",
        option_b="BB",
        correct_answer="B",
        explanation="解析二",
    )
    db.add_all([q1, q2])
    db.commit()
    return child, book, q1, q2


def test_public_questions_never_contain_answer(db):
    """用户取题接口不泄露 correct_answer/explanation（F-057 前端判分断裂根因）"""
    _, book, _, _ = _seed(db)
    svc = AdvancementService(db)
    questions = svc.get_quiz_questions(book.id, is_quiz_id=False)
    assert len(questions) == 2
    for q in questions:
        assert "correct_answer" not in q
        assert "explanation" not in q


def test_submit_response_carries_authoritative_review(db):
    """提交响应携带每题回顾：正确答案/解析/对错由服务端权威返回"""
    child, book, q1, q2 = _seed(db)
    svc = AdvancementService(db)
    quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
    result = svc.submit_answers(
        quiz.id,
        [
            {"question_id": q1.id, "answer": "A"},  # correct
            {"question_id": q2.id, "answer": "A"},  # wrong
        ],
    )
    assert result["correct"] == 1
    review = result["question_review"]
    assert len(review) == 2

    by_qid = {item["question_id"]: item for item in review}
    first = by_qid[q1.id]
    assert first["is_correct"] is True
    assert first["correct_answer"] == "A"
    assert first["selected_answer"] == "A"
    assert first["explanation"] == "解析一"

    second = by_qid[q2.id]
    assert second["is_correct"] is False
    assert second["correct_answer"] == "B"
    assert second["selected_answer"] == "A"
    assert second["explanation"] == "解析二"
    assert second["question_text"] == "Q2"
    assert second["option_a"] == "AA"
    assert second["option_b"] == "BB"


def test_review_answers_match_db_after_submit(db):
    """提交后 review 的正确答案与题库逐字一致（撤行守护：去掉 review 返回必红）"""
    child, book, q1, _ = _seed(db)
    svc = AdvancementService(db)
    quiz = svc.start_quiz(child.id, QuizStartRequest(book_id=book.id))
    result = svc.submit_answers(quiz.id, [{"question_id": q1.id, "answer": "B"}])
    review = result["question_review"]
    assert len(review) == 1
    assert review[0]["correct_answer"] == "A"
    assert review[0]["is_correct"] is False
