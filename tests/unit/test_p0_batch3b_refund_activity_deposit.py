# tests/unit/test_p0_batch3b_refund_activity_deposit.py
"""二批 P0 续批：F51-F53 + F55-F56 退款/押金/活动链

F51: 365 天退款上限统计 APPROVED+COMPLETED（COMPLETED 漏计导致循环免费试用）
F52: 管理端代客退款金额公式修正（OrderService.calculate_refund）+ 审核通过不动 pay_status
F53: 活动取消退款无支付单 → 转人工队列 + 运营告警 + 文案修正（不再"置 APPROVED 不动钱"）
F55: 押金退款回调按 DP 前缀分发 + REFUNDING 超时巡检 + refund 请求带 notify_url
F56: 管理员代缴押金取孩子监护人 openid（此前 current_user=None → 500）
"""

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import (
    DepositStatus,
    MemberStatus,
    OrderType,
    PayStatus,
)
from backend.database import Base, get_db
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


@pytest.fixture
def http_db():
    """HTTP 层 fixture：StaticPool 共享连接，供 TestClient 跨线程使用"""
    from fastapi.testclient import TestClient

    from backend.main import app

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
    client = TestClient(app)
    yield client, session
    app.dependency_overrides.clear()
    session.close()


def _mk_user_child(db, openid="p0b3b", phone="13800008888"):
    user = User(openid=openid, phone=phone)
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="P0B3B",
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
        deposit_status=DepositStatus.UNPAID,
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_order(db, user, child, order_no="MW-P0B3B-001", amount=Decimal("500.00")):
    order = Order(
        order_no=order_no,
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OBSERVATION,
        amount=amount,
        pay_status=PayStatus.PAID,
        pay_time=datetime.now(),
    )
    db.add(order)
    db.commit()
    return order


# ============================================================ F51
class TestF51AnnualLimitCountsCompleted:
    def test_completed_refund_blocks_new_application(self, db):
        """F51：COMPLETED 退款也计入 365 天上限，防买→全退→再买循环"""
        from backend.common.exceptions import ValidationError
        from backend.domain.refund.schemas import RefundCreate
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        order = _mk_order(db, user, child)
        db.add(
            RefundApplication(
                order_id=order.id,
                user_id=user.id,
                child_id=child.id,
                refund_amount=Decimal("500.00"),
                status=RefundApplication.STATUS_COMPLETED,
                create_time=datetime.now() - timedelta(days=10),
            )
        )
        db.commit()

        with pytest.raises(ValidationError, match="365"):
            RefundService(db).apply_refund(
                user.id, RefundCreate(order_id=order.id, used_days=5, reason="x")
            )


# ============================================================ F52
class TestF52AdminCreateRefund:
    def test_create_refund_uses_used_days_formula(self, db):
        """F52：金额公式走 OrderService.calculate_refund（500 用 10 天 → 466.67）"""
        from backend.domain.admin.services.refund_service import AdminRefundService

        user, child = _mk_user_child(db)
        _mk_order(db, user, child)
        result = AdminRefundService(db).create_refund(
            "MW-P0B3B-001", {"used_days": 10}, admin=None
        )
        refund = (
            db.query(RefundApplication)
            .filter(RefundApplication.id == result["refund_id"])
            .first()
        )
        assert refund.refund_amount == Decimal("466.67")
        assert refund.status == RefundApplication.STATUS_PENDING

    def test_admin_approve_does_not_mark_order_refunded(self, db):
        """F52：超管路径审核通过只置退款中，pay_status 保持 PAID（钱未退不能标已退）"""
        from types import SimpleNamespace

        from backend.domain.admin.services.refund_service import AdminRefundService

        user, child = _mk_user_child(db)
        order = _mk_order(db, user, child)
        admin = SimpleNamespace(id=1, role=0)
        result = AdminRefundService(db).create_refund(
            "MW-P0B3B-001", {"used_days": 10}, admin=admin
        )
        db.refresh(order)
        assert result["status"] == RefundApplication.STATUS_APPROVED
        assert order.pay_status == PayStatus.PAID  # 不能提前标已退款
        assert order.refund_status == 1  # 退款中


# ============================================================ F53
class TestF53ActivityCancelManualRefund:
    def test_paid_activity_cancel_goes_manual_queue(self, db):
        """F53：活动取消退款转人工队列（PENDING）+ 运营告警 + 文案改人工"""
        from backend.domain.activity.models import Activity, ActivityEnrollment
        from backend.domain.activity.service import ActivityService
        from backend.domain.message.models import SystemMessage

        user, child = _mk_user_child(db)
        activity = Activity(
            title="绘本共读",
            type=Activity.TYPE_READING,
            status=Activity.STATUS_ENROLLING,
            is_free=0,
            price=Decimal("88.00"),
            venue_id=1,
            start_time=datetime.now() + timedelta(days=2),
            end_time=datetime.now() + timedelta(days=2, hours=1),
        )
        db.add(activity)
        db.commit()
        enrollment = ActivityEnrollment(
            activity_id=activity.id,
            child_id=child.id,
            ticket_code="TC-P0B3B-001",
            status=ActivityEnrollment.STATUS_APPROVED,
        )
        db.add(enrollment)
        db.commit()

        ActivityService(db).cancel_activity(activity.id, admin_id=1)
        refund = (
            db.query(RefundApplication)
            .filter(RefundApplication.child_id == child.id)
            .first()
        )
        assert refund is not None
        assert refund.status == RefundApplication.STATUS_PENDING  # 转人工
        alert = (
            db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == 0,
                SystemMessage.title == "活动退款待人工处理",
            )
            .first()
        )
        assert alert is not None
        user_msg = (
            db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == user.id,
                SystemMessage.title == "活动取消通知",
            )
            .first()
        )
        assert "人工处理" in user_msg.content


# ============================================================ F55
class TestF55DepositRefundCallback:
    class _DepositCallbackGateway:
        def __init__(self, out_trade_no):
            self.out_trade_no = out_trade_no

        async def verify_callback_signature(self, body, signature, timestamp, nonce):
            return True

        async def decrypt_callback_data(self, ciphertext, nonce, associated_data):
            from backend.common.gateways.payment.types import PaymentCallbackData

            return PaymentCallbackData(
                out_trade_no=self.out_trade_no,
                transaction_id="TX-DP",
                refund_status="SUCCESS",
                raw_body="{}",
            )

    def test_deposit_refund_callback_dispatches_by_prefix(self, http_db):
        """F55：DP 单号退款回调 → 押金 REFUNDING → REFUNDED（此前 404 重试风暴）"""
        from backend.main import app

        client, db = http_db
        _, child = _mk_user_child(db)
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            status=DepositStatus.REFUNDING,
            pay_order_id="DP-CB-001",
            refund_time=datetime.now(),
        )
        db.add(rec)
        db.commit()

        from backend.common.dependencies import get_payment_gateway

        app.dependency_overrides[get_payment_gateway] = lambda: (
            self._DepositCallbackGateway("DP-CB-001")
        )
        try:
            r = client.post(
                "/refund/callback",
                json={
                    "resource": {
                        "ciphertext": "x",
                        "nonce": "n",
                        "associated_data": "a",
                    }
                },
            )
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 200, r.text
        db.refresh(rec)
        assert rec.status == DepositStatus.REFUNDED

    def test_stale_deposit_refunding_reverted(self, db):
        """F55：REFUNDING 超 7 天 → 回退 REFUND_PENDING + 运营告警"""
        from backend.domain.message.models import SystemMessage
        from backend.tasks.scheduler import alert_stale_refunds

        _, child = _mk_user_child(db)
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            status=DepositStatus.REFUNDING,
            pay_order_id="DP-STALE-3",
            refund_time=datetime.now() - timedelta(days=8),
        )
        db.add(rec)
        db.commit()

        alert_stale_refunds(db=db)
        db.refresh(rec)
        assert rec.status == DepositStatus.REFUND_PENDING
        alert = (
            db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == 0,
                SystemMessage.title == "押金退款超时告警（运营）",
            )
            .first()
        )
        assert alert is not None

    def test_refund_request_carries_notify_url(self, db, monkeypatch):
        """F55：退款请求携带 WECHAT_REFUND_NOTIFY_URL"""
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        _mk_order(db, user, child)

        class CapturingGateway:
            def __init__(self):
                self.refund_requests = []

            async def refund(self, request):
                self.refund_requests.append(request)
                return SimpleNamespace(success=True, refund_id="RF-N")

        gw = CapturingGateway()
        monkeypatch.setattr("backend.database.get_session", lambda: lambda: db)
        monkeypatch.setattr(
            "backend.common.dependencies.get_payment_gateway", lambda: gw
        )

        class FakeSettings:
            DEBUG = False
            WECHAT_REFUND_NOTIFY_URL = "https://example.com/refund/callback"

        monkeypatch.setattr("backend.config.get_settings", lambda: FakeSettings())

        import asyncio

        asyncio.run(
            RefundService._execute_wechat_refund(1, "MW-P0B3B-001", Decimal("500"), "x")
        )
        assert gw.refund_requests[0].notify_url == "https://example.com/refund/callback"


# ============================================================ F56
class TestF56AdminPayDeposit:
    def test_admin_pay_deposit_uses_child_guardian_openid(self, http_db):
        """F56：管理员代缴取孩子监护人 openid（此前 current_user=None → 500）"""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import AsyncMock, MagicMock

        from jose import jwt

        from backend.config import get_settings
        from backend.domain.admin.models import Admin
        from backend.domain.admin.rbac_models import Role
        from backend.main import app
        from backend.seeds.seed_rbac import (
            seed_permissions,
            seed_role_permissions,
            seed_roles,
        )

        client, db = http_db
        user, child = _mk_user_child(db, openid="p0b3b_guardian")
        seed_roles(db)
        seed_permissions(db)
        seed_role_permissions(db)
        db.flush()
        role = db.query(Role).filter(Role.code == "staff").first()
        admin = Admin(
            username="p0b3b_admin",
            name="代缴测试",
            admin_role_id=role.id,
            password_hash="x",
        )
        db.add(admin)
        db.commit()
        settings = get_settings()
        token = jwt.encode(
            {
                "sub": str(admin.id),
                "role": 1,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "type": "admin",
                "jti": "p0b3b-pay",
                "gen": 0,
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        gw = MagicMock()
        gw.supports_instant_payment = True
        gw.create_order = AsyncMock(
            return_value=MagicMock(success=True, pay_params={"prepay_id": "x"})
        )
        from backend.common.dependencies import get_payment_gateway

        app.dependency_overrides[get_payment_gateway] = lambda: gw
        try:
            r = client.post(
                "/admin/api/deposits/pay",
                json={"child_id": child.id},
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 200, r.text
        rec = db.query(DepositRecord).filter(DepositRecord.child_id == child.id).first()
        assert rec is not None
        assert rec.status == DepositStatus.PAID
        assert gw.create_order.await_args.args[0].openid == "p0b3b_guardian"
