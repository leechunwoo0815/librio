# tests/unit/test_f12_refund_callback_guard.py
"""F12 回归测试：退款回调必须校验 refund_status，非成功状态不得标记已退款

此前 /refund/callback 解密后直接 mark_refunded，不读通知体 refund_status——
微信通知"退款异常/退款关闭"时系统仍标记已退款（钱未出去，财务与业务状态双错）。
同时 mark_refunded 无幂等守卫，重复回调会重复置位。
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base, get_db
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.user.models import User
from backend.main import app


class StubRefundGateway:
    """返回指定 refund_status 的退款通知网关桩"""

    def __init__(self, refund_status: str = "SUCCESS"):
        self.refund_status = refund_status

    async def verify_callback_signature(self, body, signature, timestamp, nonce):
        return True

    async def decrypt_callback_data(self, ciphertext, nonce, associated_data):
        from backend.common.gateways.payment.types import PaymentCallbackData

        return PaymentCallbackData(
            out_trade_no="MW-F12-001",
            transaction_id="TX-F12",
            refund_status=self.refund_status,
            raw_body="{}",
        )


@pytest.fixture
def http_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.clear()
    session.close()


def _seed_order_refund(db):
    user = User(openid="f12", phone="13800007777")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F12",
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
    )
    db.add(child)
    db.commit()
    order = Order(
        order_no="MW-F12-001",
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OFFICIAL_MEMBER,
        amount=Decimal("5400"),
        pay_status=PayStatus.PAID,
    )
    db.add(order)
    db.commit()
    refund = RefundApplication(
        order_id=order.id,
        child_id=child.id,
        user_id=user.id,
        refund_amount=Decimal("100"),
        used_days=10,
        status=RefundApplication.STATUS_APPROVED,
    )
    db.add(refund)
    db.commit()
    return user, child, order, refund


class TestMarkRefundedIdempotent:
    def test_second_callback_does_not_error(self, http_db):
        from backend.domain.refund.service import RefundService

        db = http_db
        user, child, order, refund = _seed_order_refund(db)
        svc = RefundService(db)

        svc.mark_refunded("MW-F12-001")
        db.refresh(refund)
        assert refund.status == RefundApplication.STATUS_COMPLETED

        # 重复回调：幂等返回，不报错不重复置位
        svc.mark_refunded("MW-F12-001")
        db.refresh(refund)
        assert refund.status == RefundApplication.STATUS_COMPLETED


class TestRefundCallbackStatusGate:
    def test_non_success_status_not_marked(self, http_db, monkeypatch):
        """空/未知 refund_status：不标记完成、不回退、不告警（留待对账人工处理）"""
        from fastapi.testclient import TestClient

        from backend.common.dependencies import get_payment_gateway
        from backend.domain.message.models import SystemMessage

        db = http_db
        user, child, order, refund = _seed_order_refund(db)
        monkeypatch.setitem(
            app.dependency_overrides,
            get_payment_gateway,
            lambda: StubRefundGateway(refund_status=""),
        )
        client = TestClient(app)

        r = client.post(
            "/refund/callback",
            json={
                "resource": {"ciphertext": "x", "nonce": "y", "associated_data": "z"}
            },
        )

        assert r.status_code == 200
        db.refresh(refund)
        db.refresh(order)
        assert refund.status == RefundApplication.STATUS_APPROVED  # 未标记完成
        assert order.pay_status == PayStatus.PAID  # 订单未置 REFUNDED
        alerts = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == 0, SystemMessage.title == "退款异常告警")
            .count()
        )
        assert alerts == 0

    def test_success_status_marks_refunded(self, http_db, monkeypatch):
        from fastapi.testclient import TestClient

        from backend.common.dependencies import get_payment_gateway

        db = http_db
        user, child, order, refund = _seed_order_refund(db)
        monkeypatch.setitem(
            app.dependency_overrides,
            get_payment_gateway,
            lambda: StubRefundGateway(refund_status="SUCCESS"),
        )
        client = TestClient(app)

        r = client.post(
            "/refund/callback",
            json={
                "resource": {"ciphertext": "x", "nonce": "y", "associated_data": "z"}
            },
        )

        assert r.status_code == 200
        db.refresh(refund)
        db.refresh(order)
        assert refund.status == RefundApplication.STATUS_COMPLETED
        assert order.pay_status == PayStatus.REFUNDED

    def test_terminal_failure_rolls_back_to_pending_with_alert(
        self, http_db, monkeypatch
    ):
        """ABNORMAL/CLOSED 终态：回退 PENDING + 管理端告警，订单保持 PAID 可重试"""
        from fastapi.testclient import TestClient

        from backend.common.dependencies import get_payment_gateway
        from backend.domain.message.models import SystemMessage

        db = http_db
        user, child, order, refund = _seed_order_refund(db)
        monkeypatch.setitem(
            app.dependency_overrides,
            get_payment_gateway,
            lambda: StubRefundGateway(refund_status="ABNORMAL"),
        )
        client = TestClient(app)

        r = client.post(
            "/refund/callback",
            json={
                "resource": {"ciphertext": "x", "nonce": "y", "associated_data": "z"}
            },
        )

        assert r.status_code == 200
        db.refresh(refund)
        db.refresh(order)
        assert refund.status == RefundApplication.STATUS_PENDING  # 回退可重试
        assert order.pay_status == PayStatus.PAID
        assert order.refund_status == 3  # FAILED
        alerts = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == 0, SystemMessage.title == "退款异常告警")
            .count()
        )
        assert alerts == 1

    def test_processing_status_keeps_approved(self, http_db, monkeypatch):
        """PROCESSING（进行中）不回退不告警，退款单保持 APPROVED 等待最终回调"""
        from fastapi.testclient import TestClient

        from backend.common.dependencies import get_payment_gateway
        from backend.domain.message.models import SystemMessage

        db = http_db
        user, child, order, refund = _seed_order_refund(db)
        monkeypatch.setitem(
            app.dependency_overrides,
            get_payment_gateway,
            lambda: StubRefundGateway(refund_status="PROCESSING"),
        )
        client = TestClient(app)

        r = client.post(
            "/refund/callback",
            json={
                "resource": {"ciphertext": "x", "nonce": "y", "associated_data": "z"}
            },
        )

        assert r.status_code == 200
        db.refresh(refund)
        assert refund.status == RefundApplication.STATUS_APPROVED
        alerts = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == 0, SystemMessage.title == "退款异常告警")
            .count()
        )
        assert alerts == 0
