# tests/unit/test_damage_flow.py
"""批次5 损坏/丢失流程单元测试 — B9 双人复核 + B10 寻找期/回滚/换新

- B9：重度/丢失定级财务效应延迟到第二管理员复核（damage_dual_review）
- B9：复核人不能是登记人本人；复核驳回回滚物理效应
- B10：丢失登记写入 7 天寻找期；期内/期外找回均回滚（副本/库存/罚款/借阅状态）
- B10：买同 ISBN 新书归还替代赔偿（新副本入库 + 全额免赔）
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.config_service import ConfigService
import backend.common.config_audit_model  # noqa: F401
import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ValidationError
from backend.common.types import BookCopyStatus, BorrowStatus
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
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    ConfigService.invalidate()


def _setup(db, price=Decimal("100")):
    user = User(openid="df1", phone="13800000401")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="损坏", age=8, grade="三年级", status=2)
    db.add(child)
    db.commit()
    book = Book(
        isbn="DF001",
        title="易碎绘本",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=1000,
        price=price,
        total_stock=2,
        available_stock=2,
    )
    db.add(book)
    db.commit()
    copy = BookCopy(book_id=book.id, barcode="DF-001", status=BookCopyStatus.BORROWED)
    db.add(copy)
    db.commit()
    borrow = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        book_copy_id=copy.id,
        status=BorrowStatus.BORROWING,
        borrow_time=datetime.now() - timedelta(days=5),
        due_date=datetime.now() + timedelta(days=16),
    )
    db.add(borrow)
    db.commit()
    return user, child, book, copy, borrow


class TestDualReview:
    def test_heavy_needs_review_no_fine_yet(self, db):
        """重度定级：财务效应待复核，outstanding 不变"""
        _, child, _, _, borrow = _setup(db, price=Decimal("200"))
        svc = DamageAdminService(db)
        report = svc.create_report(borrow.id, damage_level=2, admin_id=1)
        assert report.status == BookDamageReport.STATUS_PENDING_REVIEW
        assert report.fine_amount == Decimal("100.00")
        db.refresh(child)
        assert (child.outstanding_fines or 0) == 0

    def test_confirm_by_second_admin_applies_fine(self, db):
        _, child, _, _, borrow = _setup(db, price=Decimal("200"))
        svc = DamageAdminService(db)
        report = svc.create_report(borrow.id, damage_level=2, admin_id=1)
        confirmed = svc.confirm_report(report.id, admin_id=2)
        assert confirmed.status == BookDamageReport.STATUS_PENDING
        db.refresh(child)
        assert child.outstanding_fines == Decimal("100.00")

    def test_same_admin_cannot_review(self, db):
        """复核人不能是登记人本人"""
        _, _, _, _, borrow = _setup(db, price=Decimal("200"))
        svc = DamageAdminService(db)
        report = svc.create_report(borrow.id, damage_level=2, admin_id=1)
        with pytest.raises(ValidationError, match="登记人本人"):
            svc.confirm_report(report.id, admin_id=1)

    def test_reject_rolls_back_lost_physical(self, db):
        """复核驳回丢失定级：副本/库存/借阅状态全部回滚"""
        _, child, book, copy, borrow = _setup(db)
        svc = DamageAdminService(db)
        report = svc.create_report(borrow.id, damage_level=3, admin_id=1)
        db.refresh(copy)
        assert copy.status == BookCopyStatus.LOST

        svc.reject_report(report.id, admin_id=2, reason="误登记")
        db.refresh(copy)
        db.refresh(book)
        db.refresh(borrow)
        assert copy.status == BookCopyStatus.AVAILABLE
        assert book.total_stock == 2
        assert book.available_stock == 2
        assert borrow.status == BorrowStatus.BORROWING
        assert borrow.lost_search_deadline is None
        db.refresh(child)
        assert (child.outstanding_fines or 0) == 0

    def test_dual_review_off_immediate_fine(self, db):
        """配置关闭双人复核 → 恢复即时生效（保留修改接口）"""
        ConfigService.set_config(db, "damage_dual_review", "false")
        _, child, _, _, borrow = _setup(db, price=Decimal("200"))
        svc = DamageAdminService(db)
        report = svc.create_report(borrow.id, damage_level=2, admin_id=1)
        assert report.status == BookDamageReport.STATUS_PENDING
        db.refresh(child)
        assert child.outstanding_fines == Decimal("100.00")


class TestLostSearchAndFound:
    def test_lost_sets_search_deadline(self, db):
        """B10：丢失登记写入 7 天寻找期"""
        _, _, _, _, borrow = _setup(db)
        svc = DamageAdminService(db)
        svc.create_report(borrow.id, damage_level=3, admin_id=1)
        db.refresh(borrow)
        assert borrow.lost_search_deadline is not None
        delta = borrow.lost_search_deadline - datetime.now()
        assert 6 <= delta.days <= 7

    def test_found_within_window_full_waiver(self, db):
        """期内找回：全额免赔 + 物理回滚 + 借阅 RETURNED"""
        _, child, book, copy, borrow = _setup(db)
        svc = DamageAdminService(db)
        report = svc.create_report(borrow.id, damage_level=3, admin_id=1)
        svc.confirm_report(report.id, admin_id=2)  # 罚款 150 生效
        db.refresh(child)
        assert child.outstanding_fines == Decimal("150.00")

        result = svc.mark_book_found(borrow.id, admin_id=2)
        assert result["within_search_window"] is True
        assert Decimal(result["waived_amount"]) == Decimal("150.00")

        db.refresh(child)
        db.refresh(copy)
        db.refresh(book)
        db.refresh(borrow)
        db.refresh(report)
        assert child.outstanding_fines == Decimal("0")
        assert copy.status == BookCopyStatus.AVAILABLE
        assert book.total_stock == 2
        assert book.available_stock == 2
        assert borrow.status == BorrowStatus.RETURNED
        assert borrow.fine_amount == Decimal("0")
        assert borrow.lost_search_deadline is None
        assert report.status == BookDamageReport.STATUS_OVERRIDDEN
        assert report.override_fine == Decimal("0")

    def test_found_beyond_window_still_rolls_back(self, db):
        """期外找回：同样回滚未缴罚款"""
        _, child, _, _, borrow = _setup(db)
        svc = DamageAdminService(db)
        report = svc.create_report(borrow.id, damage_level=3, admin_id=1)
        svc.confirm_report(report.id, admin_id=2)
        # 模拟已过寻找期
        borrow.lost_search_deadline = datetime.now() - timedelta(days=1)
        db.commit()

        result = svc.mark_book_found(borrow.id, admin_id=2)
        assert result["within_search_window"] is False
        db.refresh(child)
        assert child.outstanding_fines == Decimal("0")

    def test_found_rejects_non_lost(self, db):
        """非丢失状态不可找回"""
        _, _, _, _, borrow = _setup(db)
        svc = DamageAdminService(db)
        with pytest.raises(ValidationError, match="不是丢失状态"):
            svc.mark_book_found(borrow.id, admin_id=1)


class TestReplaceWithNewCopy:
    def test_replace_new_copy_full_flow(self, db):
        """买新书替代：新副本入库 + 全额免赔 + 借阅 RETURNED"""
        _, child, book, _, borrow = _setup(db)
        svc = DamageAdminService(db)
        report = svc.create_report(borrow.id, damage_level=3, admin_id=1)
        svc.confirm_report(report.id, admin_id=2)

        result = svc.replace_with_new_copy(borrow.id, "DF-NEW-001", admin_id=2)
        assert result["success"] is True
        assert Decimal(result["waived_amount"]) == Decimal("150.00")

        db.refresh(child)
        db.refresh(book)
        db.refresh(borrow)
        new_copy = db.query(BookCopy).filter(BookCopy.barcode == "DF-NEW-001").first()
        assert new_copy is not None
        assert new_copy.status == BookCopyStatus.AVAILABLE
        assert book.total_stock == 2  # 丢失-1 + 新增+1（净：原2-1+1=2）
        assert book.available_stock == 2
        assert borrow.status == BorrowStatus.RETURNED
        assert child.outstanding_fines == Decimal("0")

    def test_replace_rejects_duplicate_barcode(self, db):
        _, _, _, copy, borrow = _setup(db)
        svc = DamageAdminService(db)
        svc.create_report(borrow.id, damage_level=3, admin_id=1)
        with pytest.raises(ValidationError, match="已存在"):
            svc.replace_with_new_copy(borrow.id, copy.barcode, admin_id=1)
