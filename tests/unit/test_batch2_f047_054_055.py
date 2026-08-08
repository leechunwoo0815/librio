# tests/unit/test_batch2_f047_054_055.py
"""批次 2：F-047 首次免罚并发 / F-054 押金重缴拦截 / F-055 宽限期免罚额度"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ConflictError
from backend.common.fine_policy import apply_fine, get_overdue_policy
from backend.common.types import DepositStatus
from backend.database import Base
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
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


def _mk_child_with_records(db, n=2):
    user = User(openid="b2f", phone="13800002004")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="F", age=7, grade="一")
    db.add(child)
    db.commit()
    records = []
    for i in range(n):
        rec = BorrowRecord(
            child_id=child.id,
            book_id=1,
            borrow_time=datetime.now() - timedelta(days=30),
            due_date=datetime.now() - timedelta(days=10 + i),
            status=2,  # OVERDUE
        )
        db.add(rec)
        db.flush()
        records.append(rec)
    db.commit()
    return child, records


class TestF047FirstFreeOnce:
    def test_second_overdue_not_free(self, db):
        """同一孩子第二条计费逾期不再免罚（首次免罚仅一次）"""
        child, records = _mk_child_with_records(db)
        policy = get_overdue_policy(db)
        # 第一条：首次逾期 → 免罚
        apply_fine(db, records[0], days_overdue=11, policy=policy)
        assert records[0].fine_waived == 1
        # 第二条：非首次 → 正常计费
        apply_fine(db, records[1], days_overdue=12, policy=policy)
        assert records[1].fine_waived == 0
        assert records[1].fine_amount > 0


class TestF054RepayGuard:
    def test_repay_rejects_pending_record(self, db):
        user = User(openid="b2r", phone="13800002005")
        db.add(user)
        db.commit()
        child = Child(user_id=user.id, name="R", age=7, grade="一")
        db.add(child)
        db.commit()
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200"),
            original_amount=Decimal("1200"),
            status=DepositStatus.PENDING,
            pay_order_id="DP-F54",
        )
        db.add(rec)
        db.commit()
        svc = DepositService(db)
        with pytest.raises(ConflictError, match="处理中"):
            import asyncio

            asyncio.run(svc.repay_deposit(child.id, MagicMockGateway()))


class MagicMockGateway:
    supports_instant_payment = False


class TestF055GraceDoesNotConsumeFree:
    def test_grace_period_overdue_keeps_free_quota(self, db):
        """宽限期内逾期（不产生罚款）不消耗首次免罚额度"""
        child, records = _mk_child_with_records(db, n=2)
        policy = get_overdue_policy(db)  # grace_days=3
        # 第一条：宽限期内（overdue_days=2 ≤ grace=3）→ 0 罚款，不置 fine_waived
        apply_fine(db, records[0], days_overdue=2, policy=policy)
        assert records[0].fine_amount == 0
        assert records[0].fine_waived == 0
        # 第二条：真逾期（overdue_days=12 > grace）→ 仍享受首次免罚
        apply_fine(db, records[1], days_overdue=12, policy=policy)
        assert records[1].fine_waived == 1
