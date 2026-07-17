import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.book.models import Book, BookCopy
from backend.domain.advancement.models import QuestionBank
from backend.domain.borrow.models import BorrowRecord
from backend.common.types import BorrowStatus, DepositStatus
from backend.bootstrap import register_event_handlers


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


def test_bulk_import_books_deduplication(db):
    from backend.domain.admin.services.book_service import AdminBookService
    from backend.domain.admin.schemas import BulkImportBookItem

    svc = AdminBookService(db)
    items = [
        BulkImportBookItem(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                           ar_value=Decimal("3.2"), age_min=7, age_max=9),
        BulkImportBookItem(isbn="9780064400558", title="Charlotte's Web 2", author="E.B. White",
                           ar_value=Decimal("3.5"), age_min=7, age_max=9),
        BulkImportBookItem(isbn="9780061120084", title="The Little Prince", author="Saint-Exupéry",
                           ar_value=Decimal("4.0"), age_min=8, age_max=12),
    ]
    result = svc.bulk_import_books(items)
    assert result["success"] == 2
    assert result["total"] == 3
    skip_count = sum(1 for r in result["results"] if r["status"] == "skip")
    assert skip_count == 1


def test_bulk_import_questions_batch_lookup(db):
    from backend.domain.admin.services.book_service import AdminBookService
    from backend.domain.admin.schemas import BulkImportQuestionItem

    svc = AdminBookService(db)
    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=Decimal("3.2"), age_min=7, age_max=9, word_count=31000)
    db.add(book)
    db.commit()

    items = [
        BulkImportQuestionItem(isbn="9780064400558", question_text="Q1",
                               option_a="A", option_b="B", option_c="C", option_d="D",
                               correct_answer="A"),
        BulkImportQuestionItem(isbn="9780064400558", question_text="Q2",
                               option_a="A", option_b="B", option_c="C", option_d="D",
                               correct_answer="B"),
    ]
    result = svc.bulk_import_questions(items)
    assert result["success"] == 2
    assert result["total"] == 2


def test_search_questions_by_book_batch(db):
    from backend.domain.admin.services.book_service import AdminBookService

    svc = AdminBookService(db)
    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=Decimal("3.2"), age_min=7, age_max=9, word_count=31000)
    db.add(book)
    db.commit()

    for i in range(3):
        db.add(QuestionBank(book_id=book.id, question_text=f"Q{i}",
                            option_a="A", option_b="B", option_c="C", option_d="D",
                            correct_answer="A", difficulty=i))
    db.commit()

    result = svc.search_questions_by_book("Charlotte")
    assert result["total"] == 3


def test_batch_generate_copies(db):
    from backend.domain.admin.services.book_service import AdminBookService

    svc = AdminBookService(db)
    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=Decimal("3.2"), age_min=7, age_max=9, word_count=31000)
    db.add(book)
    db.commit()

    result = svc.batch_generate_copies("9780064400558", 3)
    assert result["success"] == 3
    copies = db.query(BookCopy).filter(BookCopy.book_id == book.id).all()
    assert len(copies) == 3


def test_batch_generate_copies_skip_existing(db):
    from backend.domain.admin.services.book_service import AdminBookService

    svc = AdminBookService(db)
    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=Decimal("3.2"), age_min=7, age_max=9, word_count=31000)
    db.add(book)
    db.commit()

    db.add(BookCopy(book_id=book.id, barcode="9780064400558-0001"))
    db.commit()

    result = svc.batch_generate_copies("9780064400558", 5)
    assert result["success"] == 4
    copies = db.query(BookCopy).filter(BookCopy.book_id == book.id).all()
    assert len(copies) == 5


def test_admin_list_children_borrow_counts(db):
    from backend.domain.admin.services.borrow_service import AdminBorrowService

    svc = AdminBorrowService(db)
    user = User(openid="parent1", phone="13800138001")
    db.add(user)
    db.flush()
    children = []
    for i in range(3):
        child = Child(user_id=user.id, name=f"孩子{i}", age=5 + i, grade="大班",
                      status=Child.STATUS_OFFICIAL, deposit_status=DepositStatus.PAID)
        db.add(child)
        db.flush()
        children.append(child)
    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=Decimal("3.2"), age_min=7, age_max=9, word_count=31000)
    db.add(book)
    db.flush()
    from datetime import datetime
    now = datetime.utcnow()
    db.add(BorrowRecord(child_id=children[0].id, book_id=book.id, status=BorrowStatus.BORROWING,
                        borrow_time=now, due_date=now))
    db.add(BorrowRecord(child_id=children[1].id, book_id=book.id, status=BorrowStatus.BORROWING,
                        borrow_time=now, due_date=now))
    db.add(BorrowRecord(child_id=children[1].id, book_id=book.id, status=BorrowStatus.RETURNED,
                        borrow_time=now, due_date=now))
    db.commit()

    result = svc.list_children(limit=10, child_ids=[c.id for c in children])
    counts = {r["id"]: r["current_borrow_count"] for r in result}
    assert counts[children[0].id] == 1
    assert counts[children[1].id] == 1
    assert counts[children[2].id] == 0


def test_admin_list_children_empty_input(db):
    from backend.domain.admin.services.borrow_service import AdminBorrowService

    svc = AdminBorrowService(db)
    result = svc.list_children(limit=10, child_ids=[])
    assert result == []


def test_overdue_reminders_batch_loading(db):
    from backend.domain.admin.services.message_service import AdminMessageService
    from backend.domain.admin.services.system_service import AdminSystemService
    from backend.domain.message.models import SystemMessage

    sys_svc = AdminSystemService(db)
    svc = AdminMessageService(db, system_service=sys_svc)

    user = User(openid="parent1", phone="13800138001")
    db.add(user)
    db.flush()
    child = Child(user_id=user.id, name="小明", age=7, grade="二年级",
                  status=Child.STATUS_OFFICIAL, deposit_status=DepositStatus.PAID)
    db.add(child)
    db.flush()
    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=Decimal("3.2"), age_min=7, age_max=9, word_count=31000)
    db.add(book)
    db.flush()
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    db.add(BorrowRecord(child_id=child.id, book_id=book.id, status=BorrowStatus.BORROWING,
                        borrow_time=now, due_date=now - timedelta(days=3)))
    db.commit()

    result = svc.send_overdue_reminders(user.id)
    assert result["success"] is True
    assert result["sent_count"] >= 1
    msgs = db.query(SystemMessage).filter(SystemMessage.user_id == user.id).all()
    assert len(msgs) == 1
    assert "逾期" in msgs[0].content


def test_benefit_transfer_list_batch(db):
    from backend.domain.admin.services.benefit_transfer_service import BenefitTransferAdminService

    svc = BenefitTransferAdminService(db)
    user = User(openid="parent1", phone="13800138001", parent_name="测试家长")
    db.add(user)
    db.flush()
    children = []
    for i in range(2):
        child = Child(user_id=user.id, name=f"孩子{i}", age=6, grade="一年级",
                      status=Child.STATUS_OFFICIAL, deposit_status=DepositStatus.PAID)
        db.add(child)
        db.flush()
        children.append(child)
    from backend.domain.child.benefit_transfer_model import BenefitTransferApplication
    app = BenefitTransferApplication(
        source_child_id=children[0].id, target_child_id=children[1].id,
        user_id=user.id, status=0,
    )
    db.add(app)
    db.commit()

    result = svc.get_list(status=0)
    assert result["total"] == 1
    assert result["items"][0]["source_child_name"] == "孩子0"
    assert result["items"][0]["target_child_name"] == "孩子1"
    assert result["items"][0]["user_name"] == "测试家长"
