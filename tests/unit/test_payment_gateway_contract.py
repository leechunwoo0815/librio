# tests/unit/test_payment_gateway_contract.py
"""第十二关：真实支付网关契约测试 — 业务层传入网关的金额单位必须为【分】

背景（F1/F2 修复）：generate_pay_code 与三处退款调用曾传【元】，而 WeChatPayV3 按【分】消费
（pay_v3.create_order/refund 直接 int(request.amount)）。正常支付路径与押金路径显式 ×100
佐证契约单位为分。本文件用捕获型 stub 网关钉死"元入分出"转换，防止回归。
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import (
    BorrowStatus,
    DepositStatus,
    MemberStatus,
    PayStatus,
)
from backend.database import Base
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.order.models import Order
from backend.domain.user.models import User


class CapturingGateway:
    """捕获 PaymentOrderRequest / PaymentRefundRequest 的桩网关（模拟真实微信按分消费）"""

    supports_instant_payment = False

    def __init__(self):
        self.order_request = None
        self.refund_requests = []
        self.pay_params = {
            "timeStamp": "t",
            "nonceStr": "n",
            "package": "prepay_id=x",
            "signType": "RSA",
            "paySign": "s",
        }

    async def create_order(self, request):
        self.order_request = request
        return SimpleNamespace(success=True, pay_params=self.pay_params)

    async def refund(self, request):
        self.refund_requests.append(request)
        return SimpleNamespace(success=True, refund_id="RF-TEST")


class RejectingRefundGateway:
    """F37：模拟微信拒绝（success=False，pay_v3 对被拒不抛异常）"""

    def __init__(self, error_message="订单或退款金额不一致"):
        self.error_message = error_message
        self.refund_requests = []

    async def refund(self, request):
        self.refund_requests.append(request)
        return SimpleNamespace(success=False, error_message=self.error_message)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


def _mk_user_child(db, openid="gw"):
    user = User(openid=openid, phone=f"138{abs(hash(openid)) % 10**8:08d}")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="网关",
        age=7,
        grade="二年级",
        status=MemberStatus.OFFICIAL,
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_order(
    db,
    user,
    child,
    amount=Decimal("500"),
    order_no="MW-GW-001",
    pay_status=PayStatus.PENDING,
    order_type=2,
):
    order = Order(
        order_no=order_no,
        user_id=user.id,
        child_id=child.id,
        type=order_type,
        amount=amount,
        pay_status=pay_status,
    )
    db.add(order)
    db.commit()
    return order


class TestOrderPaymentCents:
    """F1：A5 门店收款码 generate_pay_code 传分（500 元 → 50000 分）"""

    def test_generate_pay_code_passes_cents(self, db):
        from backend.domain.order.service import OrderService

        user, child = _mk_user_child(db)
        _mk_order(db, user, child, amount=Decimal("500"), order_no="MW-CENT-001")
        gw = CapturingGateway()

        asyncio.run(OrderService(db).generate_pay_code("MW-CENT-001", gw))

        assert gw.order_request is not None
        assert gw.order_request.amount == 50000  # 元入分出


class TestOrderRefundCents:
    """F2/F37：订单退款 _execute_wechat_refund 传分 + total=原单语义"""

    def test_execute_wechat_refund_passes_cents(self, db, monkeypatch):
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        _mk_order(
            db,
            user,
            child,
            amount=Decimal("500"),
            order_no="MW-REF-001",
            pay_status=PayStatus.PAID,
        )

        gw = CapturingGateway()
        monkeypatch.setattr("backend.database.get_session", lambda: lambda: db)
        monkeypatch.setattr(
            "backend.common.dependencies.get_payment_gateway", lambda: gw
        )

        class FakeSettings:
            DEBUG = False

        monkeypatch.setattr("backend.config.get_settings", lambda: FakeSettings())

        asyncio.run(
            RefundService._execute_wechat_refund(
                1, "MW-REF-001", Decimal("500"), "测试"
            )
        )

        assert gw.refund_requests
        assert gw.refund_requests[0].total_amount == 50000
        assert gw.refund_requests[0].refund_amount == 50000

    def test_partial_refund_total_is_original_amount(self, db, monkeypatch):
        """F37：部分退款 total=原单 50000 分、refund=46667 分（微信 V3 语义）"""
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        _mk_order(
            db,
            user,
            child,
            amount=Decimal("500"),
            order_no="MW-REF-PART-001",
            pay_status=PayStatus.PAID,
        )

        gw = CapturingGateway()
        monkeypatch.setattr("backend.database.get_session", lambda: lambda: db)
        monkeypatch.setattr(
            "backend.common.dependencies.get_payment_gateway", lambda: gw
        )

        class FakeSettings:
            DEBUG = False

        monkeypatch.setattr("backend.config.get_settings", lambda: FakeSettings())

        asyncio.run(
            RefundService._execute_wechat_refund(
                1, "MW-REF-PART-001", Decimal("466.67"), "部分退款"
            )
        )

        assert gw.refund_requests
        assert gw.refund_requests[0].total_amount == 50000  # 原单 500 元
        assert gw.refund_requests[0].refund_amount == 46667  # 部分退款

    def test_refund_rejection_is_not_swallowed(self, db, monkeypatch):
        """F37：网关拒绝（success=False）→ 退款单回 PENDING + 管理端告警，不再静默挂 APPROVED"""
        from backend.domain.message.models import SystemMessage
        from backend.domain.refund.models import RefundApplication
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        order = _mk_order(
            db,
            user,
            child,
            amount=Decimal("500"),
            order_no="MW-REF-REJ-001",
            pay_status=PayStatus.PAID,
        )
        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id,
            child_id=child.id,
            refund_amount=Decimal("466.67"),
            status=RefundApplication.STATUS_APPROVED,
            out_refund_no="RF-REJ-001",
        )
        db.add(refund)
        db.commit()

        gw = RejectingRefundGateway()

        class _NoCloseSession:
            """共享测试会话代理：close() 空操作，避免 _execute_wechat_refund finally 关闭会话"""

            def __init__(self, session):
                self.__session = session

            def __getattr__(self, name):
                return getattr(self.__session, name)

            def close(self):
                pass

        monkeypatch.setattr(
            "backend.database.get_session",
            lambda: lambda: _NoCloseSession(db),
        )
        monkeypatch.setattr(
            "backend.common.dependencies.get_payment_gateway", lambda: gw
        )

        class FakeSettings:
            DEBUG = False

        monkeypatch.setattr("backend.config.get_settings", lambda: FakeSettings())

        asyncio.run(
            RefundService._execute_wechat_refund(
                refund.id, order.order_no, Decimal("466.67"), "部分退款"
            )
        )

        db.expire_all()
        db.refresh(refund)
        db.refresh(order)
        assert refund.status == RefundApplication.STATUS_PENDING
        assert order.refund_status == 3  # FAILED
        alert = (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == 0, SystemMessage.title == "退款执行失败")
            .first()
        )
        assert alert is not None


class TestDepositRefundCents:
    """F2：押金退款与 600 奖励退款传分"""

    def _mk_deposit(self, db, child, amount=Decimal("1200"), status=DepositStatus.PAID):
        rec = DepositRecord(child_id=child.id, amount=amount, status=status)
        db.add(rec)
        db.commit()
        return rec

    def test_audit_refund_approve_passes_cents(self, db):
        from backend.domain.deposit.service import DepositService

        user, child = _mk_user_child(db)
        self._mk_deposit(db, child, status=DepositStatus.REFUND_PENDING)
        gw = CapturingGateway()

        asyncio.run(DepositService(db).audit_refund(child.id, "approve", 1, gw))

        assert gw.refund_requests
        assert gw.refund_requests[0].total_amount == 120000
        assert gw.refund_requests[0].refund_amount == 120000

    def test_partial_refund_passes_cents(self, db):
        from backend.domain.deposit.service import DepositService

        user, child = _mk_user_child(db)
        self._mk_deposit(db, child, amount=Decimal("1200"), status=DepositStatus.PAID)
        for i in range(10):
            db.add(
                BorrowRecord(
                    child_id=child.id,
                    book_id=i + 1,
                    borrow_time=datetime.now() - timedelta(days=30),
                    due_date=datetime.now() - timedelta(days=5),
                    status=BorrowStatus.RETURNED,
                    overdue_days=0,
                )
            )
        db.commit()
        gw = CapturingGateway()

        asyncio.run(DepositService(db).partial_refund_deposit(child.id, gw))

        assert gw.refund_requests
        assert gw.refund_requests[0].total_amount == 120000  # 原押金 1200
        assert gw.refund_requests[0].refund_amount == 60000  # 奖励退款 600


class TestCloseExpiredRace:
    """F5：订单超时关闭不得覆盖已支付订单（先付后关竞态）"""

    def test_close_does_not_overwrite_paid(self, monkeypatch):
        from backend.tasks import scheduler

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        s1 = Session()  # 关闭任务 session
        s2 = Session()  # 支付回调 session

        user = User(openid="race1", phone="13800009999")
        s2.add(user)
        s2.commit()
        child = Child(
            user_id=user.id,
            name="R",
            age=7,
            grade="二",
            status=MemberStatus.OFFICIAL,
        )
        s2.add(child)
        s2.commit()
        order = Order(
            order_no="MW-RACE-001",
            user_id=user.id,
            child_id=child.id,
            type=2,
            amount=Decimal("500"),
            pay_status=PayStatus.PENDING,
        )
        s2.add(order)
        s2.commit()
        s2.execute(
            text("UPDATE `order` SET create_time=:t WHERE order_no='MW-RACE-001'"),
            {"t": datetime.now() - timedelta(minutes=60)},
        )
        s2.commit()

        monkeypatch.setattr(scheduler, "_get_db_session", lambda: s1)
        # 模拟竞态：关闭任务查询后、commit 前，回调侧把订单置 PAID
        orig_commit = s1.commit

        def race_commit():
            s2.query(Order).filter(Order.order_no == "MW-RACE-001").update(
                {Order.pay_status: PayStatus.PAID}
            )
            s2.commit()
            orig_commit()

        s1.commit = race_commit

        scheduler.close_expired_orders()

        s2.expire_all()
        final_status = (
            s2.query(Order).filter(Order.order_no == "MW-RACE-001").one().pay_status
        )
        assert final_status == PayStatus.PAID  # 已支付订单不得被覆盖为 CLOSED
        s1.close()
        s2.close()
