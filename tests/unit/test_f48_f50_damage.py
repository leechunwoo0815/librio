# tests/unit/test_f48_f50_damage.py
"""F48-F50 损坏定责批 + F62 申诉期起点

F48: 丢失待复核（PENDING_REVIEW）期间登记找回不得冲销孩子其他合法罚款
F49: 改判丢失→重度（override 3→2）：未填金额按 0.5×定价默认；副本 DAMAGED 时 available 不得 +1
F50: 重度损坏（level 2）定级同步标记副本 DAMAGED
F62: 7 天申诉期从双人复核通过（reviewed_at）起算，而非报告创建日
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import (
    BookCopyStatus,
    BorrowStatus,
    DepositStatus,
    MemberStatus,
)
from backend.database import Base
from backend.domain.admin.services.damage_admin_service import DamageAdminService
from backend.domain.book.damage_model import BookDamageReport
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mk_lost(db, price=Decimal("100.00"), outstanding=Decimal("0.00")):
    user = User(openid="f48u", phone="13800009001")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F48",
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
        deposit_status=DepositStatus.PAID,
        outstanding_fines=outstanding,
    )
    db.add(child)
    db.commit()
    book = Book(
        isbn="978F4800001",
        title="F48 Book",
        author="A",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        price=price,
        total_stock=0,  # 丢失已扣减（mark_book_lost 后 total/available 均 -1）
        available_stock=0,
    )
    db.add(book)
    db.commit()
    copy = BookCopy(book_id=book.id, barcode="BC-F48-001", status=BookCopyStatus.LOST)
    db.add(copy)
    db.commit()
    record = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        book_copy_id=copy.id,
        status=BorrowStatus.LOST,
        borrow_time=datetime.now() - timedelta(days=10),
        due_date=datetime.now() - timedelta(days=5),
        fine_amount=Decimal("150.00"),
    )
    db.add(record)
    db.commit()
    return user, child, book, copy, record


def _mk_report(db, record, level=3, status=BookDamageReport.STATUS_PENDING_REVIEW):
    report = BookDamageReport(
        borrow_record_id=record.id,
        book_copy_id=record.book_copy_id,
        child_id=record.child_id,
        damage_level=level,
        fine_amount=Decimal("150.00"),
        status=status,
        admin_id=1,
    )
    db.add(report)
    db.commit()
    return report


class TestF48FoundNoCrossWaive:
    def test_found_pending_review_does_not_waive_other_fines(self, db):
        """F48：待复核丢失找回只物理回滚，不冲销孩子其他合法罚款"""
        _, child, book, copy, record = _mk_lost(db, outstanding=Decimal("50.00"))
        _mk_report(db, record, status=BookDamageReport.STATUS_PENDING_REVIEW)
        svc = DamageAdminService(db)
        result = svc.mark_book_found(record.id, admin_id=1)
        db.refresh(child)
        assert Decimal(result["waived_amount"]) == Decimal("0")
        assert child.outstanding_fines == Decimal("50.00")  # 其他合法罚款未被冲销
        db.refresh(copy)
        assert copy.status == BookCopyStatus.AVAILABLE  # 物理回滚仍生效

    def test_found_charged_report_waives(self, db):
        """对照：已入账（PENDING/CONFIRMED）报告找回正常冲正"""
        _, child, book, copy, record = _mk_lost(db, outstanding=Decimal("150.00"))
        _mk_report(db, record, status=BookDamageReport.STATUS_PENDING)
        svc = DamageAdminService(db)
        result = svc.mark_book_found(record.id, admin_id=1)
        db.refresh(child)
        assert child.outstanding_fines == Decimal("0.00")
        assert result["waived_amount"] == "150.00"


class TestF49OverrideLostToHeavy:
    def test_override_3_to_2_defaults_fine_and_no_available_increment(self, db):
        """F49：丢失→重度改判：未填金额按 0.5×定价（100→50）；DAMAGED 时 available 不 +1"""
        _, child, book, copy, record = _mk_lost(db, price=Decimal("100.00"))
        report = _mk_report(db, record, status=BookDamageReport.STATUS_DISPUTED)
        svc = DamageAdminService(db)
        svc.review(
            report.id,
            "override",
            override_level=2,
            admin_id=1,
        )
        db.refresh(report)
        db.refresh(copy)
        db.refresh(book)
        assert report.override_fine == Decimal("50.00")  # 0.5×100
        assert copy.status == BookCopyStatus.DAMAGED
        assert book.available_stock == 0  # DAMAGED 不可借，不 +1
        assert book.total_stock == 1  # 总库存恢复

    def test_override_3_to_1_restores_available(self, db):
        """对照：丢失→轻度改判：副本 AVAILABLE，available +1"""
        _, child, book, copy, record = _mk_lost(db, price=Decimal("100.00"))
        report = _mk_report(db, record, status=BookDamageReport.STATUS_DISPUTED)
        svc = DamageAdminService(db)
        svc.review(report.id, "override", override_level=1, admin_id=1)
        db.refresh(copy)
        db.refresh(book)
        assert copy.status == BookCopyStatus.AVAILABLE
        assert book.available_stock == 1


class TestF50HeavyDamageMarksCopy:
    def test_level2_report_marks_copy_damaged(self, db):
        """F50：重度（level 2）定级 → 副本置 DAMAGED"""
        user = User(openid="f50u", phone="13800009002")
        db.add(user)
        db.commit()
        child = Child(
            user_id=user.id,
            name="F50",
            age=7,
            grade="二年级",
            status=MemberStatus.OFFICIAL,
            deposit_status=DepositStatus.PAID,
        )
        db.add(child)
        db.commit()
        book = Book(
            isbn="978F5000001",
            title="F50 Book",
            author="A",
            ar_value=2.0,
            age_min=5,
            age_max=9,
            price=Decimal("100.00"),
            total_stock=1,
            available_stock=0,
        )
        db.add(book)
        db.commit()
        copy = BookCopy(
            book_id=book.id, barcode="BC-F50-001", status=BookCopyStatus.BORROWED
        )
        db.add(copy)
        db.commit()
        record = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            book_copy_id=copy.id,
            status=BorrowStatus.BORROWING,
            borrow_time=datetime.now() - timedelta(days=1),
            due_date=datetime.now() + timedelta(days=20),
        )
        db.add(record)
        db.commit()

        DamageAdminService(db).create_report(record.id, damage_level=2, admin_id=1)
        db.refresh(copy)
        assert copy.status == BookCopyStatus.DAMAGED
        report = (
            db.query(BookDamageReport)
            .filter(BookDamageReport.borrow_record_id == record.id)
            .first()
        )
        assert report.fine_amount == Decimal("50.00")  # 0.5×100


class TestF62AppealWindowFromReview:
    def test_appeal_window_counts_from_reviewed_at(self, db):
        """F62：创建 10 天但复核通过仅 2 天 → 申诉期未过，不可自动确认"""
        from backend.common.exceptions import ValidationError

        _, child, book, copy, record = _mk_lost(db)
        report = _mk_report(db, record, status=BookDamageReport.STATUS_PENDING)
        report.create_time = datetime.now() - timedelta(days=10)
        report.reviewed_at = datetime.now() - timedelta(days=2)
        db.commit()
        svc = DamageAdminService(db)
        with pytest.raises(ValidationError, match="申诉期未过"):
            svc.confirm_expired(report.id)

    def test_reviewed_8_days_ago_confirmable(self, db):
        """对照：复核通过已 8 天 → 自动确认"""
        _, child, book, copy, record = _mk_lost(db)
        report = _mk_report(db, record, status=BookDamageReport.STATUS_PENDING)
        report.reviewed_at = datetime.now() - timedelta(days=8)
        db.commit()
        svc = DamageAdminService(db)
        result = svc.confirm_expired(report.id)
        assert result.status == BookDamageReport.STATUS_CONFIRMED

    def test_appeal_allowed_within_reviewed_window(self, db):
        """F62：创建 10 天但复核通过仅 2 天 → 家长申诉应允许（申诉期从 reviewed_at 起算）"""
        _, child, book, copy, record = _mk_lost(db)
        report = _mk_report(db, record, status=BookDamageReport.STATUS_PENDING)
        report.create_time = datetime.now() - timedelta(days=10)
        report.reviewed_at = datetime.now() - timedelta(days=2)
        db.commit()
        svc = DamageAdminService(db)
        result = svc.appeal(report.id, "想申诉")
        assert result.status == BookDamageReport.STATUS_DISPUTED

    def test_appeal_rejected_8_days_since_review(self, db):
        """对照：复核通过已 8 天 → 家长申诉被拒"""
        from backend.common.exceptions import ValidationError

        _, child, book, copy, record = _mk_lost(db)
        report = _mk_report(db, record, status=BookDamageReport.STATUS_PENDING)
        report.create_time = datetime.now() - timedelta(days=10)
        report.reviewed_at = datetime.now() - timedelta(days=8)
        db.commit()
        svc = DamageAdminService(db)
        with pytest.raises(ValidationError, match="已超过7天申诉期"):
            svc.appeal(report.id, "想申诉")


class TestLostFineMarkerInteraction:
    def test_mark_book_lost_subsumes_overdue_fine(self, db):
        """F61/前向指引：丢失覆盖已入账逾期费——outstanding 只补差额、标记同步为丢失罚款额"""
        from backend.domain.deposit.service import DepositService

        user = User(openid="f61u", phone="13800009003")
        db.add(user)
        db.commit()
        child = Child(
            user_id=user.id,
            name="F61",
            age=7,
            grade="二年级",
            status=MemberStatus.OFFICIAL,
            deposit_status=DepositStatus.PAID,
            outstanding_fines=Decimal("5.00"),
        )
        db.add(child)
        db.commit()
        book = Book(
            isbn="978F6100001",
            title="F61 Book",
            author="A",
            ar_value=2.0,
            age_min=5,
            age_max=9,
            price=Decimal("100.00"),
            total_stock=1,
            available_stock=1,
        )
        db.add(book)
        db.commit()
        copy = BookCopy(
            book_id=book.id, barcode="BC-F61-001", status=BookCopyStatus.BORROWED
        )
        db.add(copy)
        db.commit()
        record = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            book_copy_id=copy.id,
            status=BorrowStatus.OVERDUE,
            borrow_time=datetime.now() - timedelta(days=30),
            due_date=datetime.now() - timedelta(days=6),
            fine_amount=Decimal("5.00"),
            fine_in_outstanding=Decimal("5.00"),  # 逾期费已入账
        )
        db.add(record)
        db.commit()

        DepositService(db).mark_book_lost(record.id, admin_id=1)
        db.refresh(child)
        db.refresh(record)
        assert child.outstanding_fines == Decimal("150.00")  # 5 + (150-5)，不重复计
        assert record.fine_in_outstanding == Decimal("150.00")
        assert record.status == BorrowStatus.LOST

    def test_found_after_lost_waives_and_clears_marker(self, db):
        """找回后：罚款冲正、标记清零（后续 sync delta 不失真）"""
        from backend.domain.deposit.service import DepositService

        user = User(openid="f61u2", phone="13800009004")
        db.add(user)
        db.commit()
        child = Child(
            user_id=user.id,
            name="F61b",
            age=7,
            grade="二年级",
            status=MemberStatus.OFFICIAL,
            deposit_status=DepositStatus.PAID,
        )
        db.add(child)
        db.commit()
        book = Book(
            isbn="978F6100002",
            title="F61b Book",
            author="A",
            ar_value=2.0,
            age_min=5,
            age_max=9,
            price=Decimal("100.00"),
            total_stock=1,
            available_stock=1,
        )
        db.add(book)
        db.commit()
        copy = BookCopy(
            book_id=book.id, barcode="BC-F61-002", status=BookCopyStatus.BORROWED
        )
        db.add(copy)
        db.commit()
        record = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            book_copy_id=copy.id,
            status=BorrowStatus.BORROWING,
            borrow_time=datetime.now() - timedelta(days=1),
            due_date=datetime.now() + timedelta(days=20),
        )
        db.add(record)
        db.commit()

        DepositService(db).mark_book_lost(record.id, admin_id=1)
        db.refresh(child)
        assert child.outstanding_fines == Decimal("150.00")

        from backend.domain.admin.services.damage_admin_service import (
            DamageAdminService,
        )

        _mk_report(db, record, status=BookDamageReport.STATUS_PENDING)
        DamageAdminService(db).mark_book_found(record.id, admin_id=1)
        db.refresh(child)
        db.refresh(record)
        assert child.outstanding_fines == Decimal("0.00")
        assert record.fine_amount == Decimal("0")
        assert record.fine_in_outstanding == Decimal("0")
