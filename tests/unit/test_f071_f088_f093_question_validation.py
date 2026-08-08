"""F-071/F-088/F-093 题目答案校验三入口统一测试

create（advancement schema+service）/ bulk（admin schema）/ update（advancement service）
统一规则：correct_answer 必须 A-D，且指向的选项非空。
"""

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import OrderType
from backend.database import Base
from backend.domain.admin.services.book_service import AdminBookService
from backend.domain.advancement.models import QuestionBank
from backend.domain.advancement.schemas import CreateQuestionRequest
from backend.domain.advancement.service import AdvancementService
from backend.domain.book.models import Book


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_book(db) -> Book:
    book = Book(
        isbn="9780064400558",
        title="校验书",
        author="测试作者",
        ar_value=3.0,
        age_min=7,
        age_max=9,
    )
    db.add(book)
    db.commit()
    return book


class TestF071CreateQuestion:
    def test_correct_answer_must_be_abcd(self):
        with pytest.raises(ValidationError):
            CreateQuestionRequest(
                book_id=1,
                question_text="题?",
                option_a="甲",
                option_b="乙",
                correct_answer="X",
            )

    def test_correct_answer_option_must_exist(self):
        """F-093 语义：correct_answer=C 但 option_c 为空 → 422"""
        with pytest.raises(ValidationError):
            CreateQuestionRequest(
                book_id=1,
                question_text="题?",
                option_a="甲",
                option_b="乙",
                correct_answer="C",
            )

    def test_valid_question_ok(self):
        req = CreateQuestionRequest(
            book_id=1,
            question_text="题?",
            option_a="甲",
            option_b="乙",
            option_c="丙",
            correct_answer="C",
        )
        assert req.correct_answer == "C"

    def test_service_create_still_guarded(self, db):
        """service 层兜底：畸形数据即使绕过 schema 也拒绝"""
        from backend.common.exceptions import ValidationError as BizValidationError

        book = _mk_book(db)
        svc = AdvancementService(db)
        class _Rogue:
            correct_answer = "C"
            option_a = "甲"
            option_b = "乙"
            option_c = None
            option_d = None

            def model_dump(self):
                return {
                    "book_id": book.id,
                    "question_text": "题?",
                    "option_a": "甲",
                    "option_b": "乙",
                    "option_c": None,
                    "option_d": None,
                    "correct_answer": "C",
                    "difficulty": 1,
                }

        with pytest.raises(BizValidationError):
            svc.create_question(_Rogue())


class TestF093UpdateQuestion:
    def test_update_changes_answer_to_missing_option_rejected(self, db):
        """DB 中 correct_answer=A（option_a 有值），改为 C 但 option_c 为空 → 拒绝且不落库"""
        from backend.common.exceptions import ValidationError as BizValidationError
        from backend.domain.admin.admin_schemas import UpdateQuestionRequest

        book = _mk_book(db)
        q = QuestionBank(
            book_id=book.id,
            question_text="原题",
            option_a="甲",
            option_b="乙",
            correct_answer="A",
            difficulty=1,
        )
        db.add(q)
        db.commit()

        svc = AdvancementService(db)
        with pytest.raises(BizValidationError, match="指向的选项不能为空"):
            svc.update_question(
                q.id, UpdateQuestionRequest(correct_answer="C")
            )
        db.rollback()
        db.refresh(q)
        assert q.correct_answer == "A"  # 未落库

    def test_update_clears_required_option_rejected(self, db):
        """把 option_a 清空（correct_answer 仍 A）→ 拒绝"""
        from backend.common.exceptions import ValidationError as BizValidationError
        from backend.domain.admin.admin_schemas import UpdateQuestionRequest

        book = _mk_book(db)
        q = QuestionBank(
            book_id=book.id,
            question_text="原题",
            option_a="甲",
            option_b="乙",
            correct_answer="A",
            difficulty=1,
        )
        db.add(q)
        db.commit()

        svc = AdvancementService(db)
        with pytest.raises(BizValidationError, match="指向的选项不能为空"):
            svc.update_question(
                q.id, UpdateQuestionRequest(option_a="")
            )
        db.rollback()
        db.refresh(q)
        assert q.option_a == "甲"

    def test_admin_book_service_update_guarded(self, db):
        """死代码路径（admin/book_service.update_question）同步守卫，防未来接线回归"""
        from backend.common.exceptions import ValidationError as BizValidationError
        from backend.domain.admin.admin_schemas import UpdateQuestionRequest

        book = _mk_book(db)
        q = QuestionBank(
            book_id=book.id,
            question_text="原题",
            option_a="甲",
            option_b="乙",
            correct_answer="A",
            difficulty=1,
        )
        db.add(q)
        db.commit()

        svc = AdminBookService(db)
        with pytest.raises(BizValidationError, match="指向的选项不能为空"):
            svc.update_question(q.id, UpdateQuestionRequest(correct_answer="C"))


class TestF088BulkImport:
    def test_bulk_item_correct_answer_must_be_abcd(self):
        from backend.domain.admin.admin_schemas import BulkImportQuestionItem

        with pytest.raises(ValidationError):
            BulkImportQuestionItem(
                isbn="9780064400558",
                question_text="题?",
                option_a="甲",
                option_b="乙",
                correct_answer="X",
            )

    def test_bulk_item_option_cannot_be_empty(self):
        from backend.domain.admin.admin_schemas import BulkImportQuestionItem

        with pytest.raises(ValidationError):
            BulkImportQuestionItem(
                isbn="9780064400558",
                question_text="题?",
                option_a="",
                option_b="乙",
                correct_answer="A",
            )

    def test_bulk_import_valid_ok(self, db):
        from backend.domain.admin.admin_schemas import BulkImportQuestionItem

        book = _mk_book(db)
        svc = AdminBookService(db)
        result = svc.bulk_import_questions(
            [
                BulkImportQuestionItem(
                    isbn=book.isbn,
                    question_text="批量题",
                    option_a="甲",
                    option_b="乙",
                    option_c="丙",
                    correct_answer="C",
                )
            ]
        )
        assert result["success"] == 1
