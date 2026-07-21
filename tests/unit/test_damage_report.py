"""T3.6a 图书损坏定责 — 测试"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.book.models import Book, BookCopy
from backend.domain.book.damage_model import BookDamageReport
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.user.models import User
from backend.common.types import BookCopyStatus, BorrowStatus


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _setup_book(db, price=Decimal("100")):
    book = Book(
        isbn="978-TEST-DAMAGE",
        title="Test Book",
        author="Test",
        ar_value=1.0,
        age_min=3,
        age_max=12,
        price=price,
        total_stock=2,
        available_stock=2,
    )
    db.add(book)
    db.flush()
    return book


def _setup_copy(db, book_id):
    copy = BookCopy(book_id=book_id, barcode="DAMAGE-TEST-001", status=BookCopyStatus.BORROWED)
    db.add(copy)
    db.flush()
    return copy


def _setup_borrow(db, child_id, book_id, copy_id):
    record = BorrowRecord(
        child_id=child_id,
        book_id=book_id,
        book_copy_id=copy_id,
        status=BorrowStatus.BORROWING,
        borrow_time=datetime.now(),
        due_date=datetime.now() + timedelta(days=21),
    )
    db.add(record)
    db.flush()
    return record


def _setup_child(db):
    child = Child(
        user_id=1,
        name="Test Child",
        age=8,
        grade="G2",
        status=0,
    )
    db.add(child)
    db.flush()
    return child


def _setup_user(db):
    user = User(phone="13800000000", openid="test_openid")
    db.add(user)
    db.flush()
    return user


class TestCreateDamageReport:
    def test_level_1_light(self, db_session):
        """轻度损坏（免费）"""
        user = _setup_user(db_session)
        child = _setup_child(db_session)
        book = _setup_book(db_session)
        copy = _setup_copy(db_session, book.id)
        borrow = _setup_borrow(db_session, child.id, book.id, copy.id)
        db_session.commit()

        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        svc = DamageAdminService(db_session)
        report = svc.create_report(
            borrow_record_id=borrow.id, damage_level=1,
            description="封面轻微折痕", admin_id=0,
        )
        assert report.damage_level == 1
        assert report.fine_amount == Decimal("0")
        assert report.status == BookDamageReport.STATUS_PENDING

    def test_level_2_heavy(self, db_session):
        """重度损坏（0.5×定价）"""
        user = _setup_user(db_session)
        child = _setup_child(db_session)
        book = _setup_book(db_session, price=Decimal("200"))
        copy = _setup_copy(db_session, book.id)
        borrow = _setup_borrow(db_session, child.id, book.id, copy.id)
        db_session.commit()

        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        svc = DamageAdminService(db_session)
        report = svc.create_report(
            borrow_record_id=borrow.id, damage_level=2,
            description="多页严重涂画", admin_id=0,
        )
        assert report.damage_level == 2
        assert report.fine_amount == Decimal("100.00")  # 200 × 0.5
        assert report.status == BookDamageReport.STATUS_PENDING

    def test_level_3_lost_with_d05(self, db_session):
        """丢失（1.5×定价）+ D05 联动验证 BookCopy.status → LOST"""
        user = _setup_user(db_session)
        child = _setup_child(db_session)
        book = _setup_book(db_session, price=Decimal("100"))
        copy = _setup_copy(db_session, book.id)
        borrow = _setup_borrow(db_session, child.id, book.id, copy.id)
        db_session.commit()

        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        svc = DamageAdminService(db_session)
        report = svc.create_report(
            borrow_record_id=borrow.id, damage_level=3,
            description="图书丢失", admin_id=0,
        )
        assert report.damage_level == 3
        assert report.fine_amount == Decimal("150.00")  # 100 × 1.5

        db_session.refresh(copy)
        assert copy.status == BookCopyStatus.LOST  # D05 联动

        db_session.refresh(borrow)
        assert borrow.status == BorrowStatus.LOST  # 借阅标记丢失

        db_session.refresh(book)
        assert book.total_stock == 1  # 库存扣减
        assert book.available_stock == 1

    def test_borrow_not_found(self, db_session):
        """不存在的借阅记录"""
        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        from backend.common.exceptions import NotFoundError
        svc = DamageAdminService(db_session)
        with pytest.raises(NotFoundError):
            svc.create_report(borrow_record_id=9999, damage_level=1)


class TestAppeal:
    def test_appeal_within_7_days(self, db_session):
        """7天申诉期可申诉"""
        user = _setup_user(db_session)
        child = _setup_child(db_session)
        book = _setup_book(db_session)
        copy = _setup_copy(db_session, book.id)
        borrow = _setup_borrow(db_session, child.id, book.id, copy.id)
        db_session.commit()

        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        svc = DamageAdminService(db_session)
        report = svc.create_report(
            borrow_record_id=borrow.id, damage_level=2, admin_id=0,
        )
        appealed = svc.appeal(report.id, "图书归还时并未损坏")
        assert appealed.status == BookDamageReport.STATUS_DISPUTED
        assert appealed.appeal_reason == "图书归还时并未损坏"

    def test_appeal_after_7_days_rejected(self, db_session):
        """超过7天申诉期被拒绝"""
        import time
        user = _setup_user(db_session)
        child = _setup_child(db_session)
        book = _setup_book(db_session)
        copy = _setup_copy(db_session, book.id)
        borrow = _setup_borrow(db_session, child.id, book.id, copy.id)
        db_session.commit()

        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        svc = DamageAdminService(db_session)
        report = svc.create_report(
            borrow_record_id=borrow.id, damage_level=2, admin_id=0,
        )
        # 模拟超过7天
        db_session.query(BookDamageReport).filter(
            BookDamageReport.id == report.id
        ).update({
            BookDamageReport.create_time: datetime.now() - timedelta(days=8)
        })
        db_session.commit()
        db_session.refresh(report)

        from backend.common.exceptions import ValidationError
        with pytest.raises(ValidationError, match="已超过7天申诉期"):
            svc.appeal(report.id, "申诉")


class TestReview:
    def test_review_approve(self, db_session):
        """管理员确认申诉无效（确认罚款）"""
        user = _setup_user(db_session)
        child = _setup_child(db_session)
        book = _setup_book(db_session)
        copy = _setup_copy(db_session, book.id)
        borrow = _setup_borrow(db_session, child.id, book.id, copy.id)
        db_session.commit()

        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        svc = DamageAdminService(db_session)
        report = svc.create_report(
            borrow_record_id=borrow.id, damage_level=2, admin_id=0,
        )
        svc.appeal(report.id, "申诉")
        reviewed = svc.review(report.id, action="approve", review_remark="查监控确认损坏", admin_id=1)
        assert reviewed.status == BookDamageReport.STATUS_CONFIRMED
        assert reviewed.appeal_result == "查监控确认损坏"

    def test_review_override_reversal(self, db_session):
        """申诉改判冲正 — 从重度改为轻度（罚款归零）"""
        user = _setup_user(db_session)
        child = _setup_child(db_session)
        book = _setup_book(db_session, price=Decimal("200"))
        copy = _setup_copy(db_session, book.id)
        borrow = _setup_borrow(db_session, child.id, book.id, copy.id)
        db_session.commit()

        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        svc = DamageAdminService(db_session)
        report = svc.create_report(
            borrow_record_id=borrow.id, damage_level=2, admin_id=0,
        )
        assert report.fine_amount == Decimal("100.00")

        # 申诉后冲正为轻度（免费）
        svc.appeal(report.id, "轻微折痕不应重度定级")
        reviewed = svc.review(
            report.id, action="override",
            override_level=1, override_fine=Decimal("0"),
            review_remark="改判轻度", admin_id=1,
        )
        assert reviewed.status == BookDamageReport.STATUS_OVERRIDDEN
        assert reviewed.override_level == 1
        assert reviewed.override_fine == Decimal("0")

    def test_review_override_partial(self, db_session):
        """申诉改判 — 从丢失改为重度（1.5×→0.5×）"""
        user = _setup_user(db_session)
        child = _setup_child(db_session)
        book = _setup_book(db_session, price=Decimal("100"))
        copy = _setup_copy(db_session, book.id)
        borrow = _setup_borrow(db_session, child.id, book.id, copy.id)
        db_session.commit()
        orig_total = book.total_stock

        from backend.domain.admin.services.damage_admin_service import DamageAdminService
        svc = DamageAdminService(db_session)
        report = svc.create_report(
            borrow_record_id=borrow.id, damage_level=3, admin_id=0,
        )
        assert report.fine_amount == Decimal("150.00")

        # 申诉：书找到了只是损坏
        svc.appeal(report.id, "书已找到，重度损坏")
        reviewed = svc.review(
            report.id, action="override",
            override_level=2, override_fine=Decimal("50.00"),
            review_remark="改判重度", admin_id=1,
        )
        assert reviewed.status == BookDamageReport.STATUS_OVERRIDDEN
        assert reviewed.override_level == 2
