# tests/unit/test_f084_duplicate_refund.py
"""F-084 重复打款回归测试（P2 三层修复）

根因：admin create_refund 无状态校验 + 执行链无守卫——已退款订单可重复建单再打款
（F38 单号幂等不拦新单号）。
修复三层：① create_refund 前置（pay_status + 活跃退款单查重）
② _execute_wechat_refund 执行前状态守卫（已 COMPLETED/已退款 → 不调网关）
③ 执行链 order 查询 with_for_update（与 F-053 同模式）
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ConflictError, ValidationError
from backend.common.types import AdminRole, PayStatus
from backend.database import Base
from backend.domain.admin.services.refund_service import AdminRefundService
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_paid_order(db, order_no="ORD-F084", amount=Decimal("500")):
    user = User(openid="f084user", phone="13800008401")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="F084", age=7, grade="二年级")
    db.add(child)
    db.commit()
    order = Order(
        order_no=order_no,
        user_id=user.id,
        child_id=child.id,
        type=2,  # OBSERVATION
        amount=amount,
        pay_status=PayStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(order)
    db.commit()
    return user, child, order


def _admin():
    return SimpleNamespace(id=1, role=AdminRole.ADMIN)


class TestF084CreateRefundGuard:
    def test_rejects_unpaid_order(self, db):
        _, _, order = _mk_paid_order(db)
        order.pay_status = PayStatus.PENDING
        db.commit()
        svc = AdminRefundService(db)
        with pytest.raises(ValidationError, match="未支付"):
            svc.create_refund(order.order_no, {"reason": "x", "used_days": 0}, _admin())

    def test_rejects_duplicate_refund(self, db):
        _, _, order = _mk_paid_order(db)
        existing = RefundApplication(
            order_id=order.id,
            user_id=order.user_id,
            child_id=order.child_id,
            amount=order.amount,
            refund_amount=order.amount,
            status=RefundApplication.STATUS_COMPLETED,
        )
        db.add(existing)
        db.commit()
        svc = AdminRefundService(db)
        with pytest.raises(ConflictError, match="已有退款单"):
            svc.create_refund(order.order_no, {"reason": "x", "used_days": 0}, _admin())

    def test_allows_after_rejected(self, db):
        """REJECTED 退款单不拦截——可重新发起"""
        _, _, order = _mk_paid_order(db)
        rejected = RefundApplication(
            order_id=order.id,
            user_id=order.user_id,
            child_id=order.child_id,
            amount=order.amount,
            refund_amount=order.amount,
            status=RefundApplication.STATUS_REJECTED,
        )
        db.add(rejected)
        db.commit()
        svc = AdminRefundService(db)
        result = svc.create_refund(
            order.order_no, {"reason": "x", "used_days": 0}, _admin()
        )
        assert result["success"] is True


class TestF084ExecuteGuard:
    def test_execute_skips_completed_refund(self, db, monkeypatch):
        """退款单已 COMPLETED → _execute_wechat_refund 不调网关（防重复打款）"""
        from backend.domain.refund.service import RefundService

        _, _, order = _mk_paid_order(db)
        order.refund_status = 2  # 已退款
        db.commit()
        refund = RefundApplication(
            order_id=order.id,
            user_id=order.user_id,
            child_id=order.child_id,
            amount=order.amount,
            refund_amount=order.amount,
            status=RefundApplication.STATUS_COMPLETED,
        )
        db.add(refund)
        db.commit()

        # 假 session（沿用测试库）+ 假网关（断言不被调用）
        fake_gateway = MagicMock()
        fake_gateway.refund = AsyncMock()
        monkeypatch.setattr(
            "backend.database.get_session",
            lambda: lambda: db,
        )
        monkeypatch.setattr(
            "backend.common.dependencies.get_payment_gateway",
            lambda: fake_gateway,
        )

        import asyncio

        asyncio.run(
            RefundService._execute_wechat_refund(
                refund.id, order.order_no, order.amount, "test"
            )
        )
        fake_gateway.refund.assert_not_awaited()
