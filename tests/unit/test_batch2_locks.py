# tests/unit/test_batch2_locks.py
"""批次 2 行锁/查重守卫回归：F-058/066/075/076/078/107"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.domain.parent_course_time.models  # noqa: F401
from backend.common.exceptions import ValidationError
from backend.common.types import MemberStatus
from backend.database import Base
from backend.domain.activity.models import Activity, ActivityEnrollment
from backend.domain.activity.schemas import ActivityEnrollRequest
from backend.domain.activity.service import ActivityService
from backend.domain.admin.services.benefit_transfer_service import (
    BenefitTransferAdminService,
)
from backend.domain.admin.services.damage_admin_service import DamageAdminService
from backend.domain.advancement.models import ReadingSubmission
from backend.domain.advancement.service import AdvancementService
from backend.domain.book.models import Book
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.benefit_transfer_model import BenefitTransferApplication
from backend.domain.child.models import Child
from backend.domain.deposit.models import FinePayment
from backend.domain.deposit.schemas import DepositRefundRequest
from backend.domain.deposit.service import DepositService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_user_child(db, openid="b2l", phone="13800002006"):
    user = User(openid=openid, phone=phone)
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="L", age=7, grade="一")
    db.add(child)
    db.commit()
    return user, child


class TestF058SubmissionLock:
    def test_duplicate_review_rejected(self, db):
        from backend.domain.admin.admin_schemas import ReviewSubmissionRequest

        user, child = _mk_user_child(db, "b2s", "13800002007")
        sub = ReadingSubmission(
            child_id=child.id,
            book_id=1,
            status=0,
        )
        db.add(sub)
        db.commit()
        svc = AdvancementService(db)
        svc.review_submission(sub.id, ReviewSubmissionRequest(status=1))
        with pytest.raises(ValidationError, match="已审核"):
            svc.review_submission(sub.id, ReviewSubmissionRequest(status=2))


class TestF066FinePaymentReuse:
    def test_pending_fine_payment_reused(self, db):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        user, child = _mk_user_child(db, "b2f", "13800002008")
        user.openid = "openid_f066"
        child.outstanding_fines = Decimal("100")
        db.commit()
        db.refresh(child)
        assert child.outstanding_fines == Decimal("100")
        svc = DepositService(db)
        gateway = MagicMock()
        gateway.supports_instant_payment = False  # 非即时：保持 PENDING 等回调
        gateway.create_order = AsyncMock(
            return_value=MagicMock(success=True, pay_params={"code_url": "wx://x"})
        )
        req = DepositRefundRequest(child_id=child.id)
        asyncio.run(svc.pay_fines(req, gateway, current_user=user))
        asyncio.run(svc.pay_fines(req, gateway, current_user=user))
        count = db.query(FinePayment).filter(FinePayment.child_id == child.id).count()
        assert count == 1  # 复用同一 PENDING 单（防双单）


class TestF075EnrollmentDedup:
    def test_already_enrolled_returned(self, db):
        user, child = _mk_user_child(db, "b2e", "13800002009")
        activity = Activity(
            title="活动",
            type=1,
            status=Activity.STATUS_ENROLLING,
            max_participants=100,
            current_participants=0,
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=2),
        )
        db.add(activity)
        db.commit()
        svc = ActivityService(db)
        first = svc.enroll(
            ActivityEnrollRequest(activity_id=activity.id, child_id=child.id)
        )
        assert first["status"] == "enrolled"
        second = svc.enroll(
            ActivityEnrollRequest(activity_id=activity.id, child_id=child.id)
        )
        assert second["status"] == "already_enrolled"
        count = (
            db.query(ActivityEnrollment)
            .filter(
                ActivityEnrollment.child_id == child.id,
                ActivityEnrollment.activity_id == activity.id,
            )
            .count()
        )
        assert count == 1


class TestF076BookPageDedup:
    def test_save_page_updates_not_duplicates(self, db):
        from backend.domain.book.service import BookService
        from backend.domain.reading.models import BookPage

        book = Book(
            title="书",
            author="A",
            isbn="9780000000001",
            total_stock=1,
            available_stock=1,
            offline_available=1,
            ar_value=Decimal("2.0"),
            age_min=5,
            age_max=9,
            word_count=100,
        )
        db.add(book)
        db.commit()
        svc = BookService(db)
        svc.save_book_page_admin(book.id, 1, text_content="第一版")
        svc.save_book_page_admin(book.id, 1, text_content="第二版")
        pages = (
            db.query(BookPage)
            .filter(BookPage.book_id == book.id, BookPage.page_number == 1)
            .all()
        )
        assert len(pages) == 1
        assert pages[0].text_content == "第二版"


class TestF078TransferLock:
    def test_duplicate_approve_rejected(self, db):
        user, child = _mk_user_child(db, "b2t", "13800002010")
        child.status = MemberStatus.OFFICIAL
        db.commit()
        target = Child(user_id=user.id, name="T", age=6, grade="幼")
        db.add(target)
        db.commit()
        app = BenefitTransferApplication(
            source_child_id=child.id,
            target_child_id=target.id,
            user_id=user.id,
            status=0,
        )
        db.add(app)
        db.commit()
        svc = BenefitTransferAdminService(db)
        svc.approve(app.id, reviewer_id=1)
        with pytest.raises(ValidationError, match="已处理"):
            svc.approve(app.id, reviewer_id=2)


class TestF107DamageReportDedup:
    def test_duplicate_report_rejected(self, db):

        user, child = _mk_user_child(db, "b2d", "13800002011")
        book = Book(
            title="书",
            author="A",
            isbn="9780000000002",
            total_stock=1,
            available_stock=1,
            offline_available=1,
            ar_value=Decimal("2.0"),
            age_min=5,
            age_max=9,
            word_count=100,
        )
        db.add(book)
        db.flush()
        br = BorrowRecord(
            child_id=child.id,
            book_id=book.id,
            borrow_time=datetime.now() - timedelta(days=5),
            due_date=datetime.now() + timedelta(days=10),
            status=0,
        )
        db.add(br)
        db.commit()
        svc = DamageAdminService(db)
        svc.create_report(borrow_record_id=br.id, damage_level=1, description="第一次")
        with pytest.raises(ValidationError, match="未终结"):
            svc.create_report(
                borrow_record_id=br.id, damage_level=2, description="第二次"
            )
