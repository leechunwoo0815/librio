# tests/unit/test_p3_batch.py
"""P3 后端批：F31/F32/F74/F75

F31: 观察期报告持续失败加 user_id=0 告警（7 天去重）
F32: 线下建单 amount/pay_type 必须成对（单给金额落 PENDING 且审计不触发）
F74: 押金支付回调幂等（重复回调已 PAID 直接返回）
F75-②: 退款申请写入订单原额 amount（对账缺原额此前从未落库）
F75-③: 支付回调 trade_state 非 SUCCESS 不标记已支付
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import (
    DepositStatus,
    MemberStatus,
    OrderType,
    PayStatus,
)
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mk_user_child(db, status=MemberStatus.OBSERVATION):
    user = User(openid=f"p3_{id(db)}", phone="13800009201")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="P3",
        age=7,
        grade="二年级",
        status=status,
        deposit_status=DepositStatus.PAID,
        member_expire_time=datetime.now() - timedelta(days=1),
    )
    db.add(child)
    db.commit()
    return user, child


class TestF31ReportFailureAlert:
    def test_continual_failure_alerts_operator(self, db, monkeypatch):
        """F31：报告生成失败落 user_id=0 告警，不再静默卡 OBSERVATION"""
        from backend.domain.message.models import SystemMessage
        from backend.domain.report.service import ReportService

        _, child = _mk_user_child(db)
        svc = ReportService(db)

        def _boom(child):
            raise RuntimeError("生成失败")

        monkeypatch.setattr(svc, "_generate_for_child", _boom)
        result = svc.generate_due_reports()
        assert result == []
        alert = (
            db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == 0,
                SystemMessage.title == "观察期报告生成失败",
            )
            .first()
        )
        assert alert is not None
        assert str(child.id) in alert.content


class TestF32OfflineOrderPair:
    def test_amount_without_pay_type_rejected(self):
        """F32：线下建单单给 amount 被 schema 拦截（此前落 PENDING 且审计不触发）"""
        from pydantic import ValidationError

        from backend.domain.admin.admin_schemas import AdminOfflineCreateOrderRequest

        with pytest.raises(ValidationError):
            AdminOfflineCreateOrderRequest(
                parent_name="家长",
                phone="13800009222",
                child_name="孩子",
                child_age=7,
                child_grade="二年级",
                order_type=2,
                amount=Decimal("500.00"),
            )

    def test_pay_type_without_amount_rejected(self):
        from pydantic import ValidationError

        from backend.domain.admin.admin_schemas import AdminOfflineCreateOrderRequest

        with pytest.raises(ValidationError):
            AdminOfflineCreateOrderRequest(
                parent_name="家长",
                phone="13800009223",
                child_name="孩子",
                child_age=7,
                child_grade="二年级",
                order_type=2,
                pay_type=1,
            )

    def test_pair_ok(self):
        from backend.domain.admin.admin_schemas import AdminOfflineCreateOrderRequest

        req = AdminOfflineCreateOrderRequest(
            parent_name="家长",
            phone="13800009224",
            child_name="孩子",
            child_age=7,
            child_grade="二年级",
            order_type=2,
            amount=Decimal("500.00"),
            pay_type=1,
        )
        assert req.amount == Decimal("500.00")


class TestF74DepositCallbackIdempotent:
    def test_repeated_callback_returns_paid(self, db):
        """F74：重复支付回调幂等返回，不再 404/重复置位"""
        from backend.domain.deposit.service import DepositService

        _, child = _mk_user_child(db)
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            status=DepositStatus.PAID,
            pay_order_id="DP-P3-001",
            pay_time=datetime.now(),
        )
        db.add(rec)
        db.commit()
        svc = DepositService(db)
        resp = svc.handle_callback("DP-P3-001")
        assert resp.status == DepositStatus.PAID


class TestF75:
    def test_refund_writes_order_amount(self, db):
        """F75-②：退款申请写入订单原额 amount"""
        from backend.domain.refund.schemas import RefundCreate
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        order = Order(
            order_no="MW-P3-075",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500.00"),
            pay_status=PayStatus.PAID,
            pay_time=datetime.now(),
        )
        db.add(order)
        db.commit()
        result = RefundService(db).apply_refund(
            user.id, RefundCreate(order_id=order.id, used_days=5, reason="x")
        )
        refund = (
            db.query(RefundApplication)
            .filter(RefundApplication.id == result.id)
            .first()
        )
        assert refund.amount == Decimal("500.00")

    def test_callback_non_success_not_marked_paid(self, db):
        """F75-③：支付回调 trade_state 非 SUCCESS 不标记已支付"""
        from backend.domain.order.schemas import OrderPayCallback
        from backend.domain.order.service import OrderService

        user, child = _mk_user_child(db)
        order = Order(
            order_no="MW-P3-076",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500.00"),
            pay_status=PayStatus.PENDING,
        )
        db.add(order)
        db.commit()
        OrderService(db).handle_payment_callback(
            OrderPayCallback(
                order_no="MW-P3-076",
                trade_no="TX-NOTPAY",
                amount=Decimal("500.00"),
                trade_state="CLOSED",
            )
        )
        db.refresh(order)
        assert order.pay_status == PayStatus.PENDING  # 未被标记已支付


class TestF25F21F28:
    def test_f25_leap_day_refund_window(self, db, monkeypatch):
        """F25：2/29 申请退款不再 crash（timedelta 而非 replace(year)）"""
        from datetime import datetime as dt

        from backend.domain.refund.schemas import RefundCreate
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        order = Order(
            order_no="MW-P3-077",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500.00"),
            pay_status=PayStatus.PAID,
            pay_time=datetime.now(),
        )
        db.add(order)
        db.commit()
        monkeypatch.setattr(
            "backend.domain.refund.service.datetime",
            type(
                "FakeDT",
                (),
                {
                    "now": staticmethod(lambda: dt(2028, 2, 29, 10, 0, 0)),
                    "today": staticmethod(dt.today),
                },
            ),
        )
        # 不应抛 ValueError（2/29 replace 一年前崩溃）
        RefundService(db).apply_refund(
            user.id, RefundCreate(order_id=order.id, used_days=5, reason="x")
        )

    def test_f21_transfer_target_alumni_rejected(self, db):
        """F21：ALUMNI/TRIAL 目标孩子不可作为转让接收方"""
        from backend.common.exceptions import ForbiddenError
        from backend.domain.child.service import ChildService

        user = User(openid="f21u", phone="13800009230")
        db.add(user)
        db.commit()
        source = Child(
            user_id=user.id,
            name="源",
            age=7,
            grade="二年级",
            status=MemberStatus.OFFICIAL,
        )
        db.add(source)
        target = Child(
            user_id=user.id,
            name="目标",
            age=16,
            grade="高中",
            status=MemberStatus.ALUMNI,
        )
        db.add(target)
        db.commit()
        with pytest.raises(ForbiddenError, match="无法转让"):
            ChildService(db)._validate_transfer(source.id, target.id)

    def test_f28_order_status_direction_guard(self, db):
        """F28：REFUNDED 订单不可再改状态（方向校验）"""
        from backend.common.exceptions import ValidationError
        from backend.domain.admin.services.order_service import AdminOrderService

        user, child = _mk_user_child(db)
        order = Order(
            order_no="MW-P3-078",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500.00"),
            pay_status=PayStatus.REFUNDED,
        )
        db.add(order)
        db.commit()
        with pytest.raises(ValidationError, match="不允许"):
            AdminOrderService(db).update_order_status(
                "MW-P3-078", {"pay_status": PayStatus.PAID}
            )
