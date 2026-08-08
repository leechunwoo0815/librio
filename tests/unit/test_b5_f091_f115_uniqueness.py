"""批次5 F-091/F-115 回归：场馆重名拒绝 + 副本条码查重锁

F-091: create_venue 同名拒绝（ConflictError）+ venue.name DB 唯一兜底（迁移 055）
F-115: create_book_copy_admin barcode 查重加 with_for_update（并发双建防重复条码）
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.admin.admin_schemas import CreateVenueRequest
from backend.domain.admin.models import Venue
from backend.domain.admin.services.venue_service import AdminVenueService
from backend.domain.book.models import Book, BookCopy
from backend.domain.book.service import BookService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestF091VenueUnique:
    def test_duplicate_name_rejected(self, db):
        from backend.common.exceptions import ConflictError

        svc = AdminVenueService(db)
        svc.create_venue(
            CreateVenueRequest(name="旗舰店", address="A", phone="13800009100")
        )
        with pytest.raises(ConflictError, match="已存在"):
            svc.create_venue(
                CreateVenueRequest(name="旗舰店", address="B", phone="13800009101")
            )
        assert db.query(Venue).filter(Venue.name == "旗舰店").count() == 1

    def test_soft_deleted_name_not_reusable(self, db):
        """软删场馆名不可复用（与 user.phone 全局唯一语义一致，DB unique 兜底）"""
        from backend.common.exceptions import ConflictError

        svc = AdminVenueService(db)
        v = svc.create_venue(
            CreateVenueRequest(name="老店", address="A", phone="13800009102")
        )
        svc.delete_venue(v.id)
        with pytest.raises(ConflictError, match="已存在"):
            svc.create_venue(
                CreateVenueRequest(name="老店", address="B", phone="13800009103")
            )


class TestF115BarcodeLock:
    def test_duplicate_barcode_rejected(self, db):
        from backend.common.exceptions import ConflictError

        book = Book(
            isbn="9780000000115",
            title="条码书",
            author="A",
            ar_value=Decimal("2.0"),
            age_min=5,
            age_max=9,
        )
        db.add(book)
        db.commit()
        svc = BookService(db)
        svc.create_book_copy_admin(book.id, barcode="BAR-115")
        with pytest.raises(ConflictError, match="已存在"):
            svc.create_book_copy_admin(book.id, barcode="BAR-115")
        assert db.query(BookCopy).filter_by(barcode="BAR-115").count() == 1

    def test_auto_barcode_ok(self, db):
        book = Book(
            isbn="9780000000116",
            title="自动条码书",
            author="A",
            ar_value=Decimal("2.0"),
            age_min=5,
            age_max=9,
        )
        db.add(book)
        db.commit()
        svc = BookService(db)
        result = svc.create_book_copy_admin(book.id)
        assert result["barcode"].startswith("MW-")
