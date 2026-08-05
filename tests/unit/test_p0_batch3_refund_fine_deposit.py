# tests/unit/test_p0_batch3_refund_fine_deposit.py
"""第二批审查 P0 批次：F35/F36 罚款账 + F37/F38 退款网关 + F39 押金事件

F35: mark_overdue_books 不得覆写 outstanding_fines（丢损坏/丢失罚款），只做差额增量
F36: return_book 逾期服务费必须计入 outstanding_fines（标记列防双计）
F37: 订单退款 total_amount=原单额、refund_amount=退款额；网关拒绝 success=False 必须回退
F38: out_refund_no 持久化、重试复用（订单 + 押金两处）
F39: DepositPaidEvent 仅在 is_instant 块内发布；废弃 PENDING 押金超时复位 UNPAID
"""

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import BorrowStatus, DepositStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.book.models import Book, BookCopy
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.order.models import Order
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


def _mk_user_child(db, status=2):
    user = User(openid=f"p0b3_{id(db)}", phone="13800007777")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="P0B3",
        age=7,
        grade="二年级",
        status=status,
        deposit_status=DepositStatus.UNPAID,
    )
    db.add(child)
    db.commit()
    return user, child


def _mk_book(db, price=Decimal("30.00")):
    book = Book(
        title="P0B3书",
        isbn="9787000000001",
        author="作者",
        ar_value=Decimal("2.5"),
        age_min=3,
        age_max=15,
        price=price,
        total_stock=1,
        available_stock=1,
    )
    db.add(book)
    db.commit()
    copy = BookCopy(book_id=book.id, barcode=f"CP{id(book)}", status=1)
    db.add(copy)
    db.commit()
    return book, copy


def _mk_overdue_record(
    db, child, book, copy, due_days_ago=6, status=BorrowStatus.OVERDUE
):
    """造一条逾期记录；先建一条历史逾期（RETURNED）保证非首次免罚"""
    prior = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        status=BorrowStatus.RETURNED,
        borrow_time=datetime.now() - timedelta(days=60),
        due_date=datetime.now() - timedelta(days=50),
        return_time=datetime.now() - timedelta(days=40),
        overdue_days=5,
    )
    db.add(prior)
    rec = BorrowRecord(
        child_id=child.id,
        book_id=book.id,
        book_copy_id=copy.id,
        status=status,
        borrow_time=datetime.now() - timedelta(days=30),
        due_date=datetime.now() - timedelta(days=due_days_ago),
    )
    db.add(rec)
    db.commit()
    return rec


class CapturingRefundGateway:
    """捕获退款请求，可配置 success=False"""

    def __init__(self, success=True, error_message="拒绝"):
        self.success = success
        self.error_message = error_message
        self.refund_requests = []

    async def refund(self, request):
        self.refund_requests.append(request)
        if not self.success:
            return SimpleNamespace(success=False, error_message=self.error_message)
        return SimpleNamespace(success=True, refund_id="RF-CAP")


def _patch_refund_env(monkeypatch, db, gateway):
    """monkeypatch 退款执行所需的环境（DEBUG=False + get_session + gateway）"""

    class _NoCloseSession:
        """共享测试会话代理：close() 空操作，避免 _execute_wechat_refund finally 关闭会话"""

        def __init__(self, session):
            self.__session = session

        def __getattr__(self, name):
            return getattr(self.__session, name)

        def close(self):
            pass

    monkeypatch.setattr(
        "backend.database.get_session", lambda: lambda: _NoCloseSession(db)
    )
    monkeypatch.setattr(
        "backend.common.dependencies.get_payment_gateway", lambda: gateway
    )

    class FakeSettings:
        DEBUG = False

    monkeypatch.setattr("backend.config.get_settings", lambda: FakeSettings())


# ============================================================ F35
class TestF35OverdueTaskIncremental:
    def test_task_preserves_damage_fine_and_adds_overdue_delta(self, db):
        """F35：任务后 outstanding = 损坏罚款 150 + 逾期费，不被覆写为仅逾期费"""
        from backend.tasks.scheduler import mark_overdue_books

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        rec = _mk_overdue_record(db, child, book, copy)
        child.outstanding_fines = Decimal("150.00")
        db.commit()

        mark_overdue_books(db=db)
        db.refresh(child)
        db.refresh(rec)

        assert rec.fine_amount > 0
        assert rec.fine_in_outstanding == rec.fine_amount
        assert child.outstanding_fines == Decimal("150") + rec.fine_amount

    def test_task_second_run_adds_only_growth(self, db):
        """F35：第二次跑任务只加差额，不重复计已入账部分"""
        from backend.tasks.scheduler import mark_overdue_books

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        rec = _mk_overdue_record(db, child, book, copy, due_days_ago=6)
        db.commit()

        mark_overdue_books(db=db)
        db.refresh(rec)
        db.refresh(child)
        fine1 = rec.fine_amount
        marker1 = rec.fine_in_outstanding
        outstanding1 = child.outstanding_fines
        assert marker1 == fine1

        # 模拟次日：到期日再提前 2 天 → 服务费增长
        rec.due_date = rec.due_date - timedelta(days=2)
        db.commit()
        mark_overdue_books(db=db)
        db.refresh(rec)
        db.refresh(child)

        assert rec.fine_amount > fine1
        assert rec.fine_in_outstanding == rec.fine_amount
        assert child.outstanding_fines == outstanding1 + (rec.fine_amount - fine1)


# ============================================================ F36
class TestF36ReturnBookFineAccounting:
    def test_return_overdue_book_adds_fine_to_outstanding(self, db):
        """F36：任务未跑前归还，逾期费必须进 outstanding（借阅已 RETURNED）"""
        from backend.domain.borrow.schemas import ReturnBookRequest
        from backend.domain.borrow.service import BorrowService

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        rec = _mk_overdue_record(db, child, book, copy, status=BorrowStatus.BORROWING)
        db.commit()

        BorrowService(db).return_book(ReturnBookRequest(borrow_record_id=rec.id))
        db.refresh(child)
        db.refresh(rec)

        assert rec.status == BorrowStatus.RETURNED
        assert rec.fine_amount > 0
        assert child.outstanding_fines == rec.fine_amount
        assert rec.fine_in_outstanding == rec.fine_amount

    def test_return_after_task_no_double_count(self, db):
        """F36：任务已入账后归还，outstanding 不再重复加"""
        from backend.domain.borrow.schemas import ReturnBookRequest
        from backend.domain.borrow.service import BorrowService
        from backend.tasks.scheduler import mark_overdue_books

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        rec = _mk_overdue_record(db, child, book, copy, status=BorrowStatus.OVERDUE)
        db.commit()

        mark_overdue_books(db=db)
        db.refresh(child)
        outstanding_before = child.outstanding_fines
        db.refresh(rec)
        assert rec.fine_in_outstanding == rec.fine_amount

        BorrowService(db).return_book(ReturnBookRequest(borrow_record_id=rec.id))
        db.refresh(child)
        assert child.outstanding_fines == outstanding_before


# ============================================================ F37
class TestF37RefundTotalAndSuccess:
    def _mk_refund_order(self, db, user, child, amount=Decimal("500.00")):
        order = Order(
            order_no="MW-P0B3-001",
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

    def test_partial_refund_total_is_order_amount(self, db, monkeypatch):
        """F37：total=原单 500 元、refund=466.67 元（微信 V3 语义）"""
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        self._mk_refund_order(db, user, child, amount=Decimal("500.00"))
        gw = CapturingRefundGateway()
        _patch_refund_env(monkeypatch, db, gw)

        import asyncio

        asyncio.run(
            RefundService._execute_wechat_refund(
                1, "MW-P0B3-001", Decimal("466.67"), "部分退款"
            )
        )
        assert gw.refund_requests
        assert gw.refund_requests[0].total_amount == 50000
        assert gw.refund_requests[0].refund_amount == 46667

    def test_gateway_rejection_rolls_back_to_pending(self, db, monkeypatch):
        """F37：网关拒绝（success=False）→ 退款单回 PENDING、订单 FAILED、告警落库"""
        from backend.domain.message.models import SystemMessage
        from backend.domain.refund.models import RefundApplication
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        order = self._mk_refund_order(db, user, child)
        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id,
            child_id=child.id,
            refund_amount=Decimal("466.67"),
            status=RefundApplication.STATUS_APPROVED,
            out_refund_no="RF-REJECT-1",
        )
        db.add(refund)
        order.refund_status = 1
        db.commit()

        gw = CapturingRefundGateway(success=False, error_message="订单或退款金额不一致")
        _patch_refund_env(monkeypatch, db, gw)

        import asyncio

        asyncio.run(
            RefundService._execute_wechat_refund(
                refund.id, order.order_no, Decimal("466.67"), "部分退款"
            )
        )
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
        assert "订单或退款金额不一致" in alert.content


# ============================================================ F38
class TestF38OutRefundNoPersistence:
    def test_apply_refund_persists_out_refund_no(self, db):
        """F38：自动审核通过的退款申请即生成并持久化 out_refund_no"""
        from backend.domain.refund.models import RefundApplication
        from backend.domain.refund.schemas import RefundCreate
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        order = Order(
            order_no="MW-P0B3-002",
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
            user.id, RefundCreate(order_id=order.id, used_days=5, reason="test")
        )
        assert result.status == RefundApplication.STATUS_APPROVED
        refund = (
            db.query(RefundApplication)
            .filter(RefundApplication.id == result.id)
            .first()
        )
        assert refund.out_refund_no
        assert refund.out_refund_no.startswith("RF")

    def test_retry_reuses_same_out_refund_no(self, db, monkeypatch):
        """F38：重试必须复用持久化的 out_refund_no（微信幂等键）"""
        from backend.domain.refund.models import RefundApplication
        from backend.domain.refund.service import RefundService

        user, child = _mk_user_child(db)
        order = Order(
            order_no="MW-P0B3-003",
            user_id=user.id,
            child_id=child.id,
            type=OrderType.OBSERVATION,
            amount=Decimal("500.00"),
            pay_status=PayStatus.PAID,
            pay_time=datetime.now(),
        )
        db.add(order)
        db.add(
            RefundApplication(
                order_id=order.id,
                user_id=user.id,
                child_id=child.id,
                refund_amount=Decimal("500.00"),
                status=RefundApplication.STATUS_APPROVED,
                out_refund_no="RF-PERSISTED-001",
            )
        )
        db.commit()
        gw = CapturingRefundGateway()
        _patch_refund_env(monkeypatch, db, gw)

        import asyncio

        asyncio.run(
            RefundService._execute_wechat_refund(1, order.order_no, Decimal("500"), "x")
        )
        asyncio.run(
            RefundService._execute_wechat_refund(1, order.order_no, Decimal("500"), "x")
        )
        assert len(gw.refund_requests) == 2
        assert (
            gw.refund_requests[0].out_refund_no == gw.refund_requests[1].out_refund_no
        )

    def test_deposit_refund_reuses_persisted_out_refund_no(self, db):
        """F38：押金退款失败重试复用同一 out_refund_no"""
        from backend.domain.deposit.service import DepositService

        user, child = _mk_user_child(db)
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            status=DepositStatus.REFUND_PENDING,
            pay_order_id="DP-P0B3-001",
        )
        db.add(rec)
        db.commit()

        import asyncio

        failing = CapturingRefundGateway(success=False)
        with pytest.raises(Exception):
            asyncio.run(
                DepositService(db).audit_refund(child.id, "approve", 1, failing)
            )
        db.refresh(rec)
        assert rec.status == DepositStatus.REFUND_PENDING
        assert rec.out_refund_no
        first_no = rec.out_refund_no

        gw = CapturingRefundGateway()
        asyncio.run(DepositService(db).audit_refund(child.id, "approve", 1, gw))
        assert gw.refund_requests[0].out_refund_no == first_no

    def test_deposit_partial_refund_passes_out_refund_no(self, db):
        """F38：600 奖励退款同样携带持久化 out_refund_no"""
        from backend.domain.deposit.service import DepositService
        from backend.domain.borrow.models import BorrowRecord

        user, child = _mk_user_child(db)
        book, _ = _mk_book(db)
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            status=DepositStatus.PAID,
            pay_order_id="DP-P0B3-002",
        )
        db.add(rec)
        db.commit()
        for i in range(10):
            db.add(
                BorrowRecord(
                    child_id=child.id,
                    book_id=book.id,
                    status=BorrowStatus.RETURNED,
                    borrow_time=datetime.now() - timedelta(days=30 - i),
                    due_date=datetime.now() - timedelta(days=9 - i),
                    return_time=datetime.now() - timedelta(days=8 - i),
                )
            )
        db.commit()

        gw = CapturingRefundGateway()
        import asyncio

        asyncio.run(DepositService(db).partial_refund_deposit(child.id, gw))
        assert gw.refund_requests[0].out_refund_no
        db.refresh(rec)
        assert rec.partial_refund_no == gw.refund_requests[0].out_refund_no


# ============================================================ F54/F76
class TestF54F76DepositRefundSequence:
    def test_partial_then_full_refund_no_single_number_conflict(self, db):
        """F76/F54：600 奖励退款后全额退押金——单号分列且 total 用原额（120000 分）"""
        from backend.domain.deposit.service import DepositService
        from backend.domain.borrow.models import BorrowRecord

        user, child = _mk_user_child(db)
        book, _ = _mk_book(db)
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            original_amount=Decimal("1200.00"),
            status=DepositStatus.PAID,
            pay_order_id="DP-P0B3-003",
        )
        db.add(rec)
        db.commit()
        for i in range(10):
            db.add(
                BorrowRecord(
                    child_id=child.id,
                    book_id=book.id,
                    status=BorrowStatus.RETURNED,
                    borrow_time=datetime.now() - timedelta(days=30 - i),
                    due_date=datetime.now() - timedelta(days=9 - i),
                    return_time=datetime.now() - timedelta(days=8 - i),
                )
            )
        db.commit()

        import asyncio

        gw1 = CapturingRefundGateway()
        asyncio.run(DepositService(db).partial_refund_deposit(child.id, gw1))
        db.refresh(rec)
        assert rec.partial_refunded == 1
        assert rec.amount == Decimal("600.00")
        assert rec.partial_refund_no
        assert gw1.refund_requests[0].total_amount == 120000  # 原额
        assert gw1.refund_requests[0].refund_amount == 60000

        # 全额退剩余 600：必须用新的 out_refund_no（≠ 600 奖励单号），total 仍 120000
        rec.status = DepositStatus.REFUND_PENDING
        db.commit()
        gw2 = CapturingRefundGateway()
        asyncio.run(DepositService(db).audit_refund(child.id, "approve", 1, gw2))
        db.refresh(rec)
        assert rec.out_refund_no
        assert rec.out_refund_no != rec.partial_refund_no  # F76：两笔退款单号不冲突
        assert gw2.refund_requests[0].out_refund_no == rec.out_refund_no
        assert gw2.refund_requests[0].total_amount == 120000  # F54：原支付单金额
        assert gw2.refund_requests[0].refund_amount == 60000

    def test_full_refund_direct_uses_original_amount(self, db):
        """F54：未走 600 奖励的直接全额退款 total=原额 120000 分"""
        from backend.domain.deposit.service import DepositService

        user, child = _mk_user_child(db)
        rec = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            original_amount=Decimal("1200.00"),
            status=DepositStatus.REFUND_PENDING,
            pay_order_id="DP-P0B3-004",
        )
        db.add(rec)
        db.commit()

        gw = CapturingRefundGateway()
        import asyncio

        asyncio.run(DepositService(db).audit_refund(child.id, "approve", 1, gw))
        assert gw.refund_requests[0].total_amount == 120000
        assert gw.refund_requests[0].refund_amount == 120000


# ============================================================ F77
class TestF77BackfillNoDoubleCount:
    def test_backfilled_marker_prevents_double_count(self, db):
        """F77：迁移回填 marker=fine 后，首跑任务不再把老罚款重复计入"""
        from sqlalchemy import text

        from backend.tasks.scheduler import mark_overdue_books

        _, child = _mk_user_child(db)
        book, copy = _mk_book(db)
        rec = _mk_overdue_record(db, child, book, copy)
        # 模拟旧逻辑状态：任务已把 3 元计入 outstanding，但标记列=0
        from backend.common.fine_policy import calc_fine, get_overdue_policy

        fine = calc_fine(6, book.price, get_overdue_policy(db))  # (6-3)×1 = 3
        rec.fine_amount = fine
        rec.fine_in_outstanding = Decimal("0")
        child.outstanding_fines = fine
        db.commit()

        # 执行迁移 047 的回填 UPDATE
        db.execute(
            text(
                "UPDATE borrow_record SET fine_in_outstanding = fine_amount "
                "WHERE status = 2 AND fine_in_outstanding = 0 AND is_deleted = 0"
            )
        )
        db.commit()
        db.refresh(rec)
        assert rec.fine_in_outstanding == fine

        mark_overdue_books(db=db)
        db.refresh(child)
        assert child.outstanding_fines == fine  # 不双计


# ============================================================ F78
class TestF78StalePendingOnDemandReset:
    def test_pay_deposit_resets_stale_pending(self, db):
        """F78：废弃 PENDING（超窗口）再次缴纳自动复位 UNPAID 并新开支付单"""
        from unittest.mock import AsyncMock, MagicMock

        from backend.domain.deposit.schemas import DepositPayRequest
        from backend.domain.deposit.service import DepositService

        user, child = _mk_user_child(db)
        old = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            original_amount=Decimal("1200.00"),
            status=DepositStatus.PENDING,
            pay_order_id="DP-STALE-2",
            create_time=datetime.now() - timedelta(hours=3),
        )
        db.add(old)
        db.commit()

        gw = MagicMock()
        gw.supports_instant_payment = True
        gw.create_order = AsyncMock(
            return_value=MagicMock(success=True, pay_params={"prepay_id": "x"})
        )
        import asyncio

        asyncio.run(
            DepositService(db).pay_deposit(
                DepositPayRequest(child_id=child.id), gw, current_user=user
            )
        )
        db.refresh(old)
        assert old.status == DepositStatus.UNPAID
        new_rec = (
            db.query(DepositRecord)
            .filter(
                DepositRecord.child_id == child.id,
                DepositRecord.status == DepositStatus.PAID,
            )
            .first()
        )
        assert new_rec is not None
        assert new_rec.id != old.id

    def test_pay_deposit_fresh_pending_still_conflicts(self, db):
        """F78：未超窗口的 PENDING 仍按"已缴纳"拦截（防重复开单）"""
        from unittest.mock import AsyncMock, MagicMock

        from backend.common.exceptions import ConflictError
        from backend.domain.deposit.schemas import DepositPayRequest
        from backend.domain.deposit.service import DepositService

        user, child = _mk_user_child(db)
        fresh = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            original_amount=Decimal("1200.00"),
            status=DepositStatus.PENDING,
            pay_order_id="DP-FRESH-2",
            create_time=datetime.now(),
        )
        db.add(fresh)
        db.commit()

        gw = MagicMock()
        gw.supports_instant_payment = True
        gw.create_order = AsyncMock(
            return_value=MagicMock(success=True, pay_params={"prepay_id": "x"})
        )
        import asyncio

        with pytest.raises(ConflictError):
            asyncio.run(
                DepositService(db).pay_deposit(
                    DepositPayRequest(child_id=child.id), gw, current_user=user
                )
            )


# ============================================================ F39
class TestF39DepositPaidEventInstantOnly:
    def _pay(self, db, gw, user, child):
        from backend.domain.deposit.schemas import DepositPayRequest
        from backend.domain.deposit.service import DepositService

        return DepositService(db).pay_deposit(
            DepositPayRequest(child_id=child.id), gw, current_user=user
        )

    def test_non_instant_no_eligibility(self, db):
        """F39：非即时网关（生产 prepay）不得提前给借书资格"""
        from unittest.mock import AsyncMock, MagicMock

        from backend.common.types import DepositStatus

        user, child = _mk_user_child(db)
        gw = MagicMock()
        gw.supports_instant_payment = False
        gw.create_order = AsyncMock(
            return_value=MagicMock(success=True, pay_params={"prepay_id": "x"})
        )

        import asyncio

        asyncio.run(self._pay(db, gw, user, child))
        db.refresh(child)
        record = (
            db.query(DepositRecord).filter(DepositRecord.child_id == child.id).first()
        )
        # 记录保持 PENDING 等回调；孩子押金状态绝不能变 PAID
        assert record.status == DepositStatus.PENDING
        assert child.deposit_status != DepositStatus.PAID

    def test_instant_still_grants_eligibility(self, db):
        """F39：即时网关（mock/开发）行为保持不变"""
        from unittest.mock import AsyncMock, MagicMock

        from backend.common.types import DepositStatus

        user, child = _mk_user_child(db)
        gw = MagicMock()
        gw.supports_instant_payment = True
        gw.create_order = AsyncMock(
            return_value=MagicMock(success=True, pay_params={"prepay_id": "x"})
        )

        import asyncio

        asyncio.run(self._pay(db, gw, user, child))
        db.refresh(child)
        assert child.deposit_status == DepositStatus.PAID

    def test_stale_pending_deposit_reset_to_unpaid(self, db):
        """F39：废弃 PENDING 押金超时复位 UNPAID，可重新缴纳"""
        from backend.domain.deposit.service import DepositService

        user, child = _mk_user_child(db)
        old = DepositRecord(
            child_id=child.id,
            amount=Decimal("1200.00"),
            status=DepositStatus.PENDING,
            pay_order_id="DP-STALE-1",
            create_time=datetime.now() - timedelta(hours=3),
        )
        db.add(old)
        fresh = DepositRecord(
            child_id=1,
            amount=Decimal("1200.00"),
            status=DepositStatus.PENDING,
            pay_order_id="DP-FRESH-1",
            create_time=datetime.now(),
        )
        db.add(fresh)
        db.commit()

        DepositService(db).reset_stale_pending_deposits()
        db.refresh(old)
        db.refresh(fresh)
        assert old.status == DepositStatus.UNPAID
        assert fresh.status == DepositStatus.PENDING
