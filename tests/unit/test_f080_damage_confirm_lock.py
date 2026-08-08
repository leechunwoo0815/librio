# tests/unit/test_f080_damage_confirm_lock.py
"""F-080 损坏报告双计罚款回归测试

根因：confirm/reject/review 先查后改无行锁——并发双确认双计罚款。
修复：_get_report_or_raise 加 with_for_update（SQLite 单测验证状态守卫逻辑；
并发串行化由 scripts/verify_mysql_concurrency.py 场景 D 实证，RED 40/20 → GREEN 20/20）。
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ValidationError
from backend.database import Base
from backend.domain.admin.services.damage_admin_service import DamageAdminService
from backend.domain.book.damage_model import BookDamageReport
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


def _mk_pending_report(db):
    user = User(openid="f080user", phone="13800008001")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F080",
        age=7,
        grade="二年级",
        status=2,
        outstanding_fines=Decimal("0"),
    )
    db.add(child)
    db.flush()
    br = BorrowRecord(
        child_id=child.id,
        book_id=1,
        borrow_time=datetime.now() - timedelta(days=10),
        due_date=datetime.now() - timedelta(days=5),
        status=0,
    )
    db.add(br)
    db.flush()
    report = BookDamageReport(
        child_id=child.id,
        borrow_record_id=br.id,
        damage_level=2,
        fine_amount=Decimal("100"),
        status=BookDamageReport.STATUS_PENDING_REVIEW,
        description="F080 测试",
    )
    db.add(report)
    db.commit()
    return child, report


class TestF080DamageConfirm:
    def test_single_confirm_applies_fine_once(self, db):
        child, report = _mk_pending_report(db)
        DamageAdminService(db).confirm_report(report.id, admin_id=1)
        db.refresh(child)
        db.refresh(report)
        assert child.outstanding_fines == Decimal("100")
        assert report.status == BookDamageReport.STATUS_PENDING

    def test_second_confirm_blocked_by_status_guard(self, db):
        """确认后状态已迁移 → 第二管理员再确认被拦截（罚款不双计）"""
        child, report = _mk_pending_report(db)
        svc = DamageAdminService(db)
        svc.confirm_report(report.id, admin_id=1)
        with pytest.raises(ValidationError, match="仅待复核状态"):
            svc.confirm_report(report.id, admin_id=2)
        db.refresh(child)
        assert child.outstanding_fines == Decimal("100")
