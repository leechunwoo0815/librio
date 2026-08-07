# tests/unit/test_partial_refund_callback.py
"""600 奖励部分退款回调分发（F76-P2）——按 out_refund_no 精确区分部分/全额退款

背景：partial_refund_deposit（600 奖励）成功后 record 保持 PAID（余额已扣减、
partial_refunded=1）。微信 V3 退款结果通知携带 out_refund_no，但回调此前只按
out_trade_no 的 DP 前缀分发 → 部分退款回调误走 mark_refunded → 状态非 REFUNDING
→ ConflictError 409 → 微信无限重试风暴，且部分退款到账从未确认。
修复：PaymentCallbackData 增加 out_refund_no；回调按退款单号精确分发——
partial_refund_no 匹配 → 幂等确认（不改状态）；out_refund_no 匹配 → 全额退款。
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
from backend.common.types import DepositStatus
from backend.database import Base, get_db
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.user.models import User
from backend.common.dependencies import get_payment_gateway
from backend.main import app
from fastapi.testclient import TestClient


class StubRefundGateway:
    def __init__(self, out_trade_no="", out_refund_no="", refund_status="SUCCESS"):
        self.out_trade_no = out_trade_no
        self.out_refund_no = out_refund_no
        self.refund_status = refund_status

    async def verify_callback_signature(self, body, signature, timestamp, nonce):
        return True

    async def decrypt_callback_data(self, ciphertext, nonce, associated_data):
        from backend.common.gateways.payment.types import PaymentCallbackData

        return PaymentCallbackData(
            out_trade_no=self.out_trade_no,
            out_refund_no=self.out_refund_no,
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


_gateway = StubRefundGateway()


def _mk_deposit(db, status=DepositStatus.PAID, **kw):
    user = User(openid="prc", phone="13800008888")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="PRC", age=7, grade="一年级")
    db.add(child)
    db.commit()
    rec = DepositRecord(
        child_id=child.id,
        amount=Decimal("600.00"),
        original_amount=Decimal("1200.00"),
        status=status,
        pay_order_id="DP-MAIN-001",
        **kw,
    )
    db.add(rec)
    db.commit()
    return child, rec


def _post_callback(monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_payment_gateway, lambda: _gateway)
    client = TestClient(app)
    resp = client.post(
        "/refund/callback",
        json={"resource": {"ciphertext": "{}", "nonce": "n", "associated_data": "a"}},
    )
    return resp


class TestPartialRefundCallback:
    def test_partial_refund_callback_acknowledged_not_conflict(
        self, http_db, monkeypatch
    ):
        """600 奖励退款回调 → 幂等确认，不 409，押金保持 PAID"""
        _, rec = _mk_deposit(
            http_db,
            partial_refunded=1,
            partial_refund_no="DPRF-PART-001",
        )
        _gateway.out_trade_no = "DP-MAIN-001"
        _gateway.out_refund_no = "DPRF-PART-001"
        _gateway.refund_status = "SUCCESS"

        resp = _post_callback(monkeypatch)
        assert resp.status_code == 200, resp.text
        http_db.refresh(rec)
        assert rec.status == DepositStatus.PAID  # 部分退款不改变押金状态
        assert rec.amount == Decimal("600.00")  # 余额不回滚
        assert rec.partial_refunded == 1

    def test_full_refund_callback_marks_refunded(self, http_db, monkeypatch):
        """全额押金退款回调（out_refund_no 匹配）→ REFUNDING → REFUNDED"""
        _, rec = _mk_deposit(
            http_db,
            DepositStatus.REFUNDING,
            out_refund_no="DPRF-FULL-001",
            refund_amount=Decimal("600.00"),
        )
        _gateway.out_trade_no = "DP-MAIN-001"
        _gateway.out_refund_no = "DPRF-FULL-001"
        _gateway.refund_status = "SUCCESS"

        resp = _post_callback(monkeypatch)
        assert resp.status_code == 200, resp.text
        http_db.refresh(rec)
        assert rec.status == DepositStatus.REFUNDED

    def test_order_refund_callback_unaffected(self, http_db, monkeypatch):
        """订单退款回调（非 DP）不受影响"""
        # 直接复用 F12 场景最小集：非 DP out_trade_no + 无押金记录 → 走订单退款路径
        _gateway.out_trade_no = "MW-ORDER-001"
        _gateway.out_refund_no = "RF-ORDER-001"
        _gateway.refund_status = "SUCCESS"
        resp = _post_callback(monkeypatch)
        # 订单不存在 → 404（与改动前一致，证明订单路径未受干扰）
        assert resp.status_code == 404
