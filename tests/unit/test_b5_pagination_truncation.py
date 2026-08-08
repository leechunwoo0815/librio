"""批次5 分页/截断/统计口径（F-094/101/102/104/108/117/118）"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import BorrowStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.activity.models import Activity
from backend.domain.advancement.models import ReadingSubmission
from backend.domain.admin.models import OperationLog, Teacher, Venue
from backend.domain.admin.services.book_service import AdminBookService
from backend.domain.admin.services.system_service import AdminSystemService
from backend.domain.admin.services.user_service import AdminUserService
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestHasNextContract:
    """F-101/F-102：5 处管理端列表必须返回 has_next"""

    def test_benefit_transfer_has_next(self, db):
        from backend.domain.admin.services.benefit_transfer_service import (
            BenefitTransferAdminService,
        )
        from backend.domain.child.benefit_transfer_model import (
            BenefitTransferApplication,
        )

        for i in range(25):
            db.add(
                BenefitTransferApplication(
                    source_child_id=1,
                    target_child_id=2,
                    user_id=1,
                )
            )
        db.commit()
        result = BenefitTransferAdminService(db).get_list(page=1, page_size=20)
        assert result["total"] == 25
        assert result["has_next"] is True

    def test_operation_logs_has_next(self, db):
        for i in range(25):
            db.add(
                OperationLog(
                    admin_id=0,
                    module="test",
                    operation="op",
                    content=f"log {i}",
                )
            )
        db.commit()
        svc = AdminSystemService(db)
        p1 = svc.list_operation_logs(page=1, page_size=20)
        p2 = svc.list_operation_logs(page=2, page_size=20)
        assert p1["total"] == 25
        assert p1["has_next"] is True
        assert p2["has_next"] is False

    def test_user_list_has_next(self, db):
        for i in range(25):
            db.add(User(openid=f"hn{i}", phone=f"138000100{i:02d}"))
        db.commit()
        result = AdminUserService(db).list_users_with_children(page=1, page_size=20)
        assert result["has_next"] is True


class TestF104RecycleBinPagination:
    def test_cross_module_total_and_paging(self, db):
        # 3 个模块各 10 条软删 → 全量 30，首页 20，第二页 10
        for i in range(10):
            db.add(
                Teacher(
                    name=f"师{i}",
                    phone=f"138000200{i:02d}",
                    venue_id=1,
                    is_deleted=1,
                )
            )
            db.add(
                Venue(
                    name=f"馆{i}",
                    address="A",
                    phone=f"138000201{i:02d}",
                    is_deleted=1,
                )
            )
            db.add(
                Activity(
                    title=f"活动{i}",
                    type=1,
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(hours=1),
                    is_deleted=1,
                )
            )
        db.commit()
        svc = AdminSystemService(db)
        p1 = svc.list_recycle_bin(page=1, page_size=20)
        p2 = svc.list_recycle_bin(page=2, page_size=20)
        assert p1["total"] == 30
        assert len(p1["items"]) == 20
        assert p1["has_next"] is True
        assert len(p2["items"]) == 10
        assert p2["has_next"] is False


class TestF094BookCopiesPagination:
    def test_page_breaks_500_limit(self, db):
        book = Book(
            isbn="9780000000940",
            title="分页书",
            author="A",
            ar_value=Decimal("2.0"),
            age_min=5,
            age_max=9,
        )
        db.add(book)
        db.commit()
        db.bulk_save_objects(
            [BookCopy(book_id=book.id, barcode=f"BC-{i:04d}") for i in range(25)]
        )
        db.commit()
        svc = AdminBookService(db)
        p1 = svc.list_bookcopies(page=1, page_size=20)
        p2 = svc.list_bookcopies(page=2, page_size=20)
        assert p1["total"] == 25
        assert len(p1["items"]) == 20
        assert p1["has_next"] is True
        assert len(p2["items"]) == 5
        assert p2["has_next"] is False


class TestF117PendingPagination:
    def test_pending_page_breaks_100(self, db):
        user = User(openid="p117", phone="13800011700")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="审", age=7, grade="二年级")
        db.add(child)
        db.commit()
        db.bulk_save_objects(
            [
                ReadingSubmission(
                    child_id=child.id,
                    book_id=1,
                    status=0,
                    submitted_at=datetime.now(),
                )
                for _ in range(25)
            ]
        )
        db.commit()
        svc = AdminUserService(db)
        p1 = svc.list_pending_submissions(page=1, page_size=20)
        p2 = svc.list_pending_submissions(page=2, page_size=20)
        assert p1["total"] == 25
        assert len(p1["items"]) == 20
        assert p1["has_next"] is True
        assert len(p2["items"]) == 5


class TestF108ExportTruncationNotice:
    def test_csv_contains_truncation_notice(self, db, monkeypatch):
        from backend.domain.admin.services import export_service

        # 10001 条书籍数据量可控（SQLite bulk），验证超限提示行
        db.bulk_save_objects(
            [
                Book(
                    isbn=f"978{i:010d}",
                    title=f"书{i}",
                    author="A",
                    ar_value=Decimal("2.0"),
                    age_min=5,
                    age_max=9,
                )
                for i in range(10001)
            ]
        )
        db.commit()
        csv_content, filename = export_service.AdminExportService(db).export_data(
            "books"
        )
        assert "[截断提示]" in csv_content
        assert "10001" in csv_content
        assert filename == "books_export.csv"


class TestF118DetailStatsFullCount:
    def test_stats_not_truncated_at_50(self, db):
        user = User(openid="p118", phone="13800011800")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="详", age=7, grade="二年级")
        db.add(child)
        db.commit()
        now = datetime.now()
        db.bulk_save_objects(
            [
                Order(
                    order_no=f"MW-P118-{i:03d}",
                    user_id=user.id,
                    child_id=child.id,
                    type=OrderType.OFFICIAL_MEMBER,
                    amount=Decimal("100"),
                    pay_status=PayStatus.PAID,
                    pay_time=now,
                )
                for i in range(60)
            ]
        )
        db.bulk_save_objects(
            [
                BorrowRecord(
                    child_id=child.id,
                    book_id=1,
                    status=BorrowStatus.BORROWING
                    if i % 2 == 0
                    else BorrowStatus.OVERDUE,
                    borrow_time=now,
                    due_date=now,
                )
                for i in range(60)
            ]
        )
        db.commit()
        detail = AdminUserService(db).get_user_detail(user.id)
        assert detail["borrow_stats"]["total"] == 60
        assert detail["borrow_stats"]["current"] == 30
        assert detail["borrow_stats"]["overdue"] == 30
        assert Decimal(detail["summary"]["total_spent"]) == Decimal("6000")
        # 展示列表仍为最近 50 条（展示 vs 统计分离）
        assert len(detail["orders"]) == 50


class TestF103PermanentDeleteGuard:
    def test_book_with_copies_rejected(self, db):
        from backend.common.exceptions import ConflictError
        from backend.domain.admin.services.system_service import AdminSystemService
        from backend.domain.book.models import BookCopy

        book = Book(
            isbn="9780000001030",
            title="关联书",
            author="A",
            ar_value=Decimal("2.0"),
            age_min=5,
            age_max=9,
            is_deleted=1,
        )
        db.add(book)
        db.commit()
        db.add(BookCopy(book_id=book.id, barcode="F103-001", is_deleted=1))
        db.commit()

        with pytest.raises(ConflictError, match="副本"):
            AdminSystemService(db).permanent_delete_item("book", book.id)
        assert db.query(Book).filter_by(id=book.id).count() == 1

    def test_orphan_book_deletable(self, db):
        from backend.domain.admin.services.system_service import AdminSystemService

        book = Book(
            isbn="9780000001031",
            title="孤书",
            author="A",
            ar_value=Decimal("2.0"),
            age_min=5,
            age_max=9,
            is_deleted=1,
        )
        db.add(book)
        db.commit()
        result = AdminSystemService(db).permanent_delete_item("book", book.id)
        assert result["success"] is True
