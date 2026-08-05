# backend/domain/deposit/service.py
"""押金域业务逻辑 — V3.1 状态机管理

UNPAID → PAID → REFUNDED / DEDUCTED
       → PENDING → PAID (真实网关路径)
"""

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.common.events import DepositPaidEvent, event_bus
from backend.common.exceptions import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from backend.domain.child.service import assert_no_pending_transfer
from backend.common.gateways.payment import (
    PaymentGateway,
    PaymentOrderRequest,
    PaymentRefundRequest,
    yuan_to_cents,
)
from backend.common.types import BookCopyStatus, BorrowStatus, DepositStatus
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.deposit.repository import DepositRepository
from backend.domain.deposit.schemas import (
    DepositPayRequest,
    DepositRefundRequest,
    DepositDeductRequest,
    DepositPayResponse,
    DepositResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_DEPOSIT_AMOUNT = Decimal("1200.00")


class DepositService:
    """押金服务 — 状态机管理"""

    def __init__(self, db: Session):
        self.db = db
        self.deposit_repo = DepositRepository(db)

    def _generate_order_no(self) -> str:
        return f"DP{uuid.uuid4().hex[:24].upper()}"

    async def pay_deposit(
        self,
        data: DepositPayRequest,
        payment_gateway: PaymentGateway,
        current_user=None,
    ) -> DepositResponse:
        """缴纳押金 — 三段式（防事务悬挂）

        架构意图：
          1. 创建PENDING记录 → commit释放行锁
          2. 事务外调用支付网关
          3. 独立事务更新最终状态
        """
        from backend.common.config_service import ConfigService
        from backend.domain.user.models import User

        existing = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if existing:
            # F78：废弃 PENDING 支付单（超时未回调）先复位 UNPAID，允许重新缴纳——
            # 否则用户放弃支付后永久被"押金已缴纳"拦截
            from backend.common.types import DepositStatus as _DS

            if existing.status == _DS.PENDING and self._is_pending_stale(existing):
                existing.status = _DS.UNPAID
                self.db.commit()
            else:
                raise ConflictError("押金已缴纳")

        deposit_amount = ConfigService.get_decimal(
            self.db, "deposit_amount", DEFAULT_DEPOSIT_AMOUNT
        )

        user = self.db.query(User).filter(User.id == current_user.id).first()
        if not user or not user.openid:
            raise ValidationError("用户openid不存在")

        order_no = self._generate_order_no()

        # Phase 1: 创建 PENDING 记录 → commit，释放行锁
        record = DepositRecord(
            child_id=data.child_id,
            amount=deposit_amount,
            original_amount=deposit_amount,  # F54：原支付单金额快照
            status=DepositStatus.PENDING,
            pay_order_id=order_no,
        )
        self.db.add(record)
        self.db.commit()

        # Phase 2: 事务外调用支付网关（无DB锁）
        amount_cent = int(deposit_amount * 100)
        order_req = PaymentOrderRequest(
            out_trade_no=order_no,
            amount=amount_cent,
            description="押金",
            openid=user.openid,
            attach="deposit",
        )
        try:
            result = await payment_gateway.create_order(order_req)
        except Exception as e:
            logger.error(f"pay_deposit gateway error: child={data.child_id}, error={e}")
            record = (
                self.db.query(DepositRecord)
                .filter(DepositRecord.id == record.id)
                .with_for_update()
                .first()
            )
            if record:
                record.status = DepositStatus.UNPAID
            self.db.commit()
            raise PaymentError(f"支付网关调用失败: {e}")

        if not result.success:
            record = (
                self.db.query(DepositRecord)
                .filter(DepositRecord.id == record.id)
                .with_for_update()
                .first()
            )
            if record:
                record.status = DepositStatus.UNPAID
            self.db.commit()
            raise PaymentError(result.error_message)

        # Phase 3: 独立事务更新最终状态
        record = (
            self.db.query(DepositRecord)
            .filter(DepositRecord.id == record.id)
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError("押金记录不存在")

        # 检查是否已被回调处理（handle_callback 已将 PENDING → PAID）
        if record.status == DepositStatus.PAID:
            self.db.commit()
            return DepositPayResponse(
                deposit=DepositResponse.model_validate(record),
                pay_params=result.pay_params,
            )

        is_instant = payment_gateway.supports_instant_payment
        if is_instant:
            record.status = DepositStatus.PAID
            record.pay_time = datetime.now()
            # F39：DepositPaidEvent 仅在即时支付路径发布——生产网关 prepay 成功≠已付款，
            # 借书资格必须等微信回调（handle_callback）才生效
            event_bus.publish(
                DepositPaidEvent(
                    child_id=data.child_id,
                    deposit_id=record.id,
                    amount=deposit_amount,
                ),
                db=self.db,
            )

        self.db.commit()
        return DepositPayResponse(
            deposit=DepositResponse.model_validate(record),
            pay_params=result.pay_params,
        )

    def handle_callback(
        self, order_no: str, amount: Decimal | None = None
    ) -> DepositResponse:
        """支付回调 — PENDING → PAID"""
        record = (
            self.db.query(DepositRecord)
            .filter(
                DepositRecord.pay_order_id == order_no,
                DepositRecord.status == DepositStatus.PENDING,
                DepositRecord.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError(f"未找到押金记录 order_no={order_no}")

        if amount is not None and amount != record.amount:
            from backend.common.exceptions import PaymentError

            raise PaymentError(f"押金金额不一致: 回调{amount}, 记录{record.amount}")

        record.status = DepositStatus.PAID
        record.pay_time = datetime.now()
        self.deposit_repo.update(record)

        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child:
            child.deposit_status = DepositStatus.PAID

        event_bus.publish(
            DepositPaidEvent(
                child_id=record.child_id,
                deposit_id=record.id,
                amount=record.amount,
            ),
            db=self.db,
        )

        self.db.commit()
        return DepositResponse.model_validate(record)

    async def repay_deposit(
        self,
        child_id: int,
        payment_gateway: PaymentGateway,
        current_user=None,
    ) -> DepositResponse:
        """重新缴纳押金（DEDUCTED/REFUNDED → PAID），三段式（防事务悬挂）

        架构意图：
          1. 创建PENDING记录 → commit释放行锁
          2. 事务外调用支付网关
          3. 独立事务更新最终状态
        """
        from backend.common.config_service import ConfigService
        from backend.domain.user.models import User

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")

        existing = self.deposit_repo.get_active_by_child_for_update(child_id)
        if existing and existing.status == DepositStatus.PAID:
            raise ConflictError("押金已缴纳，无需重复缴纳")

        deposit_amount = ConfigService.get_decimal(
            self.db, "deposit_amount", DEFAULT_DEPOSIT_AMOUNT
        )

        user = self.db.query(User).filter(User.id == child.user_id).first()
        if not user or not user.openid:
            raise ValidationError("用户openid不存在")

        order_no = self._generate_order_no()

        # Phase 1: 创建 PENDING 记录 → commit，释放行锁
        record = DepositRecord(
            child_id=child_id,
            amount=deposit_amount,
            status=DepositStatus.PENDING,
            pay_order_id=order_no,
        )
        self.db.add(record)
        self.db.flush()
        child.deposit_status = DepositStatus.PENDING
        self.db.commit()

        # Phase 2: 事务外调用支付网关（无DB锁）
        amount_cent = int(deposit_amount * 100)
        order_req = PaymentOrderRequest(
            out_trade_no=order_no,
            amount=amount_cent,
            description="押金（重新缴纳）",
            openid=user.openid,
            attach="deposit",
        )
        try:
            result = await payment_gateway.create_order(order_req)
        except Exception as e:
            logger.error(f"repay_deposit gateway error: child={child_id}, error={e}")
            record = (
                self.db.query(DepositRecord)
                .filter(DepositRecord.id == record.id)
                .with_for_update()
                .first()
            )
            if record:
                record.status = DepositStatus.UNPAID
            self.db.commit()
            raise PaymentError(f"支付网关调用失败: {e}")

        if not result.success:
            record = (
                self.db.query(DepositRecord)
                .filter(DepositRecord.id == record.id)
                .with_for_update()
                .first()
            )
            if record:
                record.status = DepositStatus.UNPAID
            self.db.commit()
            raise PaymentError(result.error_message)

        # Phase 3: 独立事务更新最终状态
        record = (
            self.db.query(DepositRecord)
            .filter(DepositRecord.id == record.id)
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError("押金记录不存在")

        # 检查是否已被回调处理（handle_callback 已将 PENDING → PAID）
        if record.status == DepositStatus.PAID:
            self.db.commit()
            return DepositPayResponse(
                deposit=DepositResponse.model_validate(record),
                pay_params=result.pay_params,
            )

        is_instant = payment_gateway.supports_instant_payment
        if is_instant:
            record.status = DepositStatus.PAID
            record.pay_time = datetime.now()
            child = (
                self.db.query(Child)
                .filter(Child.id == child_id, Child.is_deleted == 0)
                .with_for_update()
                .first()
            )
            if child:
                child.deposit_status = DepositStatus.PAID
            event_bus.publish(
                DepositPaidEvent(
                    child_id=child_id,
                    deposit_id=record.id,
                    amount=deposit_amount,
                ),
                db=self.db,
            )

        self.db.commit()
        return DepositPayResponse(
            deposit=DepositResponse.model_validate(record),
            pay_params=result.pay_params,
        )

    def refund_deposit(self, data: DepositRefundRequest) -> DepositResponse:
        """申请退还押金 — B11：未缴罚款记账累计、退押金时自动抵扣（不再拦截）；
        E1：满足条件由路由层自动审核通过"""
        record = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")

        assert_no_pending_transfer(self.db, data.child_id)

        active_borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == data.child_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .with_for_update()
            .count()
        )
        if active_borrows > 0:
            raise ValidationError(
                f"请先归还所有借阅图书（当前 {active_borrows} 本未还）"
            )

        child = (
            self.db.query(Child)
            .filter(Child.id == data.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )

        # B11：未缴罚款从押金中自动抵扣，退余额（不用先缴）
        outstanding = (
            Decimal(str(child.outstanding_fines))
            if child and child.outstanding_fines
            else Decimal("0")
        )
        record.refund_amount = max(Decimal("0"), record.amount - outstanding)
        record.status = DepositStatus.REFUND_PENDING
        self.deposit_repo.update(record)

        if child:
            child.deposit_status = DepositStatus.REFUND_PENDING

        self.db.commit()
        logger.info(
            f"Refund requested: child_id={data.child_id}, status=REFUND_PENDING, "
            f"refund_amount={record.refund_amount} (fines deducted={outstanding})"
        )
        return DepositResponse.model_validate(record)

    def deduct_deposit(self, data: DepositDeductRequest) -> DepositResponse:
        """扣除押金 — 仅允许 PAID 状态下扣除

        若罚款金额超过押金余额，则全额扣除押金，超出部分转为未缴罚款（outstanding_fines）。
        """
        record = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")
        if record.status != DepositStatus.PAID:
            raise ConflictError(f"当前状态({record.status})不允许扣除，仅 PAID 可扣除")

        # 罚款超押金：扣满押金，超出记 outstanding_fines
        actual_deduct = min(data.amount, record.amount)
        remaining_fine = data.amount - actual_deduct

        record.status = DepositStatus.DEDUCTED
        record.deduct_amount = actual_deduct
        record.deduct_reason = data.reason
        self.deposit_repo.update(record)

        child = (
            self.db.query(Child)
            .filter(Child.id == data.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child:
            child.deposit_status = DepositStatus.DEDUCTED
            # 押金抵扣后的剩余罚款记入 outstanding_fines
            child.outstanding_fines = (child.outstanding_fines or 0) + remaining_fine

        self.db.commit()
        logger.info(
            f"Deposit deducted: child={data.child_id}, "
            f"amount={data.amount}, actual_deduct={actual_deduct}, "
            f"remaining_fine={remaining_fine}"
        )
        return DepositResponse.model_validate(record)

    def mark_book_lost(self, borrow_record_id: int, admin_id: int) -> dict:
        """图书丢失登记 — 更新借阅状态 + 计算罚款"""
        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus
        from backend.common.config_service import ConfigService
        from backend.domain.book.models import Book, BookCopy

        record = (
            self.db.query(BorrowRecord)
            .filter(BorrowRecord.id == borrow_record_id, BorrowRecord.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError("借阅记录不存在")
        if record.status not in (BorrowStatus.BORROWING, BorrowStatus.OVERDUE):
            raise ValidationError(f"当前状态({record.status})不允许标记丢失")

        multiplier = ConfigService.get_decimal(
            self.db, "lost_book_fine_multiplier", Decimal("1.5")
        )
        book = self.db.query(Book).filter(Book.id == record.book_id).first()
        book_price = book.price if book and book.price else Decimal("0")
        fine_amount = book_price * multiplier

        record.status = BorrowStatus.LOST
        record.fine_amount = fine_amount

        # B10：丢失寻找期（默认 7 天，期内找回免赔）
        search_days = ConfigService.get_int(self.db, "lost_search_days", 7)
        record.lost_search_deadline = datetime.now() + timedelta(days=search_days)

        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child:
            child.outstanding_fines = (child.outstanding_fines or 0) + fine_amount

        # D05 联动：丢失标记 → BookCopy.status = LOST
        if record.book_copy_id:
            self.db.query(BookCopy).filter(BookCopy.id == record.book_copy_id).update(
                {BookCopy.status: BookCopyStatus.LOST},
                synchronize_session="fetch",
            )

        if book:
            self.db.query(Book).filter(Book.id == record.book_id).update(
                {
                    Book.total_stock: func.greatest(Book.total_stock - 1, 0),
                    Book.available_stock: func.greatest(Book.available_stock - 1, 0),
                },
                synchronize_session="fetch",
            )

        self.db.commit()
        logger.info(
            f"Book lost: borrow_id={borrow_record_id}, fine={fine_amount}, admin_id={admin_id}"
        )
        return {
            "success": True,
            "borrow_record_id": borrow_record_id,
            "fine_amount": str(fine_amount),
        }

    async def audit_refund(
        self,
        child_id: int,
        action: str,
        admin_id: int,
        payment_gateway: PaymentGateway | None = None,
    ) -> DepositResponse:
        """审核押金退款 — 三段式（防事务悬挂）

        approve 触发真实退款，reject 回退 PAID。
        架构意图：
          1. approve 先设 REFUNDING → commit 释放行锁
          2. 事务外调用退款网关
          3. 成功保持 REFUNDING，失败回退 REFUND_PENDING
        """
        record = self.deposit_repo.get_active_by_child_for_update(child_id)
        if not record:
            raise NotFoundError("未找到押金记录")
        if record.status != DepositStatus.REFUND_PENDING:
            raise ConflictError(
                f"当前状态({record.status})不允许审核，仅 REFUND_PENDING 可审核"
            )

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )

        if action == "reject":
            record.status = DepositStatus.PAID
            record.refund_time = None
            record.refund_amount = None
            if child:
                child.deposit_status = DepositStatus.PAID
            self.deposit_repo.update(record)
            self.db.commit()

            from backend.domain.admin.services.system_service import AdminSystemService

            system_service = AdminSystemService(self.db)
            system_service.write_operation_log(
                admin_id=admin_id,
                module="deposit",
                operation="refund_reject",
                content=f"押金退款审核 [reject]: 孩子 #{child_id}",
            )
            return DepositResponse.model_validate(record)

        elif action != "approve":
            raise ValidationError(f"未知审核动作: {action}，仅支持 approve/reject")

        # === approve ===

        active_borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .with_for_update()
            .count()
        )
        if active_borrows > 0:
            raise ValidationError(f"该孩子有 {active_borrows} 本未还书，请先归还再退款")

        # Phase 1: 设 REFUNDING → commit，释放行锁
        # B11：refund_amount 已在申请时按（押金-未缴罚款）预设，此处尊重预设值
        record.status = DepositStatus.REFUNDING
        record.refund_time = datetime.now()
        if not record.out_refund_no:
            # F38：审核通过时生成并持久化退款单号，失败重试复用（微信幂等键）
            record.out_refund_no = f"DPRF{uuid.uuid4().hex[:16]}"
        record.refund_amount = (
            record.refund_amount if record.refund_amount is not None else record.amount
        )
        if child:
            child.deposit_status = DepositStatus.REFUNDING
        self.deposit_repo.update(record)
        self.db.commit()

        # Phase 2: 事务外调用退款网关（无DB锁）
        if payment_gateway:
            deposit_id = record.id
            try:
                result = await payment_gateway.refund(
                    PaymentRefundRequest(
                        out_trade_no=str(record.pay_order_id)
                        if record.pay_order_id
                        else "",
                        out_refund_no=str(record.out_refund_no),
                        total_amount=Decimal(
                            yuan_to_cents(record.original_amount or record.amount)
                        ),  # F54：原支付单金额
                        refund_amount=Decimal(yuan_to_cents(record.refund_amount)),
                        reason="押金退款（审核通过）",
                        notify_url=self._refund_notify_url(),
                    )
                )
                if hasattr(result, "success") and not result.success:
                    raise PaymentError(
                        getattr(result, "error_message", "退款接口返回失败")
                    )
            except Exception as e:
                logger.error(f"Refund failed: child={child_id}, error={e}")
                # Phase 3 (failure): 回退 REFUND_PENDING，允许管理员重试
                record = (
                    self.db.query(DepositRecord)
                    .filter(DepositRecord.id == deposit_id)
                    .with_for_update()
                    .first()
                )
                if record and record.status == DepositStatus.REFUNDING:
                    record.status = DepositStatus.REFUND_PENDING
                    self.db.commit()
                raise PaymentError(f"押金退款调用失败: {e}")

        # Phase 3 (success): 保持 REFUNDING，等待 mark_refunded 或回调
        from backend.domain.admin.services.system_service import AdminSystemService

        system_service = AdminSystemService(self.db)
        system_service.write_operation_log(
            admin_id=admin_id,
            module="deposit",
            operation="refund_approve",
            content=f"押金退款审核 [approve]: 孩子 #{child_id}",
        )
        return DepositResponse.model_validate(record)

    def cancel_refund(self, child_id: int) -> DepositResponse:
        """取消退款申请 — REFUNDING/REFUND_PENDING → PAID"""
        record = self.deposit_repo.get_active_by_child_for_update(child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")
        if record.status not in (DepositStatus.REFUNDING, DepositStatus.REFUND_PENDING):
            raise ConflictError("当前状态不是退款中或待审核，无法取消")

        record.status = DepositStatus.PAID
        record.refund_time = None
        record.refund_amount = None

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child:
            child.deposit_status = DepositStatus.PAID

        self.db.commit()
        return DepositResponse.model_validate(record)

    def mark_refunded(self, child_id: int) -> DepositResponse:
        """标记押金已到账退款 — REFUNDING → REFUNDED；B11：核销已抵扣的未缴罚款"""
        record = self.deposit_repo.get_active_by_child_for_update(child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")
        if record.status != DepositStatus.REFUNDING:
            raise ConflictError("当前状态不是退款中，无法标记到账")

        record.status = DepositStatus.REFUNDED
        record.refund_time = record.refund_time or datetime.now()
        record.refund_amount = (
            record.refund_amount if record.refund_amount is not None else record.amount
        )

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child:
            child.deposit_status = DepositStatus.REFUNDED
            # B11：抵扣部分（押金-实退）从未缴罚款中核销
            deducted = record.amount - record.refund_amount
            if deducted > 0 and child.outstanding_fines:
                child.outstanding_fines = max(
                    Decimal("0"), child.outstanding_fines - deducted
                )

        self.db.commit()
        return DepositResponse.model_validate(record)

    def mark_refunded_by_order_no(self, order_no: str) -> DepositResponse:
        """F55：微信退款回调按支付单号标记押金到账（DP 前缀）"""
        record = (
            self.db.query(DepositRecord)
            .filter(
                DepositRecord.pay_order_id == order_no,
                DepositRecord.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if not record:
            raise NotFoundError(f"未找到押金支付单 {order_no}")
        return self.mark_refunded(record.child_id)

    async def partial_refund_deposit(
        self, child_id: int, payment_gateway: PaymentGateway | None = None
    ) -> DepositResponse:
        """A2：借满 N 本且无逾期记录 → 可申请减半退还押金（默认 600 元，一次为限）

        配置：deposit_partial_refund_books（默认10）、deposit_partial_refund_amount（默认600）
        """
        record = self.deposit_repo.get_active_by_child_for_update(child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")
        if record.status != DepositStatus.PAID:
            raise ConflictError("仅已缴纳状态的押金可申请减半退还")
        if record.partial_refunded:
            raise ConflictError("已享受过押金减半退还，每个孩子限一次")

        from backend.common.config_service import ConfigService

        books_needed = ConfigService.get_int(
            self.db, "deposit_partial_refund_books", 10
        )
        refund_amt = ConfigService.get_decimal(
            self.db, "deposit_partial_refund_amount", Decimal("600")
        )

        returned_count = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.status == BorrowStatus.RETURNED,
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )
        if returned_count < books_needed:
            raise ValidationError(
                f"借满 {books_needed} 本并归还后可申请减半退还（当前 {returned_count} 本）"
            )

        overdue_count = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.overdue_days > 0,
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )
        if overdue_count > 0:
            raise ValidationError("存在逾期记录，暂不符合减半退还条件")

        if record.amount < refund_amt:
            raise ValidationError(
                f"押金余额 {record.amount} 元，不足退还 {refund_amt} 元"
            )

        # Phase 1: 先落库（扣减押金余额 + 标记），commit 释放行锁
        record.amount = record.amount - refund_amt
        record.partial_refunded = 1
        if not record.partial_refund_no:
            # F76：600 奖励退款独立单号（与全额退款 out_refund_no 分列，防微信幂等冲突）
            record.partial_refund_no = f"DPRF{uuid.uuid4().hex[:16]}"
        self.deposit_repo.update(record)
        self.db.commit()

        # Phase 2: 事务外调用退款网关，失败回滚标记
        if payment_gateway:
            try:
                result = await payment_gateway.refund(
                    PaymentRefundRequest(
                        out_trade_no=str(record.pay_order_id)
                        if record.pay_order_id
                        else "",
                        out_refund_no=str(record.partial_refund_no),
                        total_amount=Decimal(
                            yuan_to_cents(
                                record.original_amount or (record.amount + refund_amt)
                            )
                        ),  # F54：原支付单金额
                        refund_amount=Decimal(yuan_to_cents(refund_amt)),
                        reason="押金减半退还（10本无逾期奖励）",
                        notify_url=self._refund_notify_url(),
                    )
                )
                if hasattr(result, "success") and not result.success:
                    raise PaymentError(
                        getattr(result, "error_message", "退款接口返回失败")
                    )
            except Exception as e:
                logger.error(f"Partial refund failed: child={child_id}, error={e}")
                record = (
                    self.db.query(DepositRecord)
                    .filter(DepositRecord.id == record.id)
                    .with_for_update()
                    .first()
                )
                if record and record.partial_refunded:
                    record.amount = record.amount + refund_amt
                    record.partial_refunded = 0
                    self.db.commit()
                raise PaymentError(f"押金减半退还调用失败: {e}")

        logger.info(
            f"Partial deposit refund: child={child_id}, amount={refund_amt}, "
            f"remaining={record.amount}"
        )
        return DepositResponse.model_validate(record)

    async def pay_fines(
        self,
        data: DepositRefundRequest,
        payment_gateway: PaymentGateway,
        current_user=None,
    ) -> dict:
        """B12：线上缴纳罚款（未缴罚款全额缴清，支付成功 outstanding_fines 归零）"""
        import uuid

        from backend.domain.deposit.models import FinePayment
        from backend.domain.user.models import User

        child = (
            self.db.query(Child)
            .filter(Child.id == data.child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")
        outstanding = child.outstanding_fines or Decimal("0")
        if outstanding <= 0:
            raise ValidationError("当前没有未缴罚款")

        user = self.db.query(User).filter(User.id == current_user.id).first()
        if not user or not user.openid:
            raise ValidationError("用户openid不存在")

        # 防重：存在进行中的缴款单则复用
        pending = (
            self.db.query(FinePayment)
            .filter(
                FinePayment.child_id == data.child_id,
                FinePayment.status == FinePayment.STATUS_PENDING,
                FinePayment.amount == outstanding,
                FinePayment.is_deleted == 0,
            )
            .first()
        )
        if pending:
            record = pending
        else:
            record = FinePayment(
                child_id=data.child_id,
                amount=outstanding,
                status=FinePayment.STATUS_PENDING,
                pay_order_no=f"FINE{uuid.uuid4().hex[:20].upper()}",
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)

        amount_cent = int(outstanding * 100)
        order_req = PaymentOrderRequest(
            out_trade_no=record.pay_order_no,
            amount=amount_cent,
            description="逾期服务费缴纳",
            openid=user.openid,
            attach="fine_payment",
        )
        try:
            result = await payment_gateway.create_order(order_req)
        except Exception as e:
            logger.error(f"pay_fines gateway error: child={data.child_id}, error={e}")
            raise PaymentError(f"支付网关调用失败: {e}")
        if not result.success:
            raise PaymentError(result.error_message)

        # Mock/即时支付环境直接核销
        if payment_gateway.supports_instant_payment:
            self._settle_fine_payment(record)
            self.db.commit()

        return {
            "fine_payment_id": record.id,
            "amount": str(record.amount),
            "pay_params": result.pay_params,
        }

    def handle_fine_callback(self, order_no: str) -> bool:
        """罚款支付回调 — 按 pay_order_no 核销

        幂等语义（P2-4）：已支付单重复回调返回 True（视为成功，避免微信重试 500）；
        仅当单号完全不存在时返回 False（让调用方走押金链路）。
        """
        from backend.domain.deposit.models import FinePayment

        record = (
            self.db.query(FinePayment)
            .filter(
                FinePayment.pay_order_no == order_no,
                FinePayment.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if not record:
            return False
        if record.status == FinePayment.STATUS_PAID:
            return True  # 重复回调幂等成功
        self._settle_fine_payment(record)
        self.db.commit()
        return True

    def _settle_fine_payment(self, record) -> None:
        """核销罚款：缴款单→已支付，child.outstanding_fines 归零（不自行 commit）"""
        from backend.domain.deposit.models import FinePayment

        record.status = FinePayment.STATUS_PAID
        record.pay_time = datetime.now()
        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child:
            paid = record.amount
            child.outstanding_fines = max(
                Decimal("0"), (child.outstanding_fines or Decimal("0")) - paid
            )
        logger.info(
            f"Fine settled: child={record.child_id}, amount={record.amount}, "
            f"order={record.pay_order_no}"
        )

    def reset_stale_pending_deposits(self, expire_minutes: int | None = None) -> int:
        """F39：废弃 PENDING 押金（超时未回调）复位 UNPAID，允许重新缴纳

        生产网关 prepay 成功≠已付款，用户放弃支付后 PENDING 记录若不复位，
        get_active_by_child 会把该记录视为活跃 → 永久阻塞再次缴纳。
        超时窗口默认 150 分钟（配置 deposit_pending_expire_minutes，须大于微信支付单有效期）。
        """
        minutes = expire_minutes or self._pending_expire_minutes()
        stale = (
            self.db.query(DepositRecord)
            .filter(
                DepositRecord.status == DepositStatus.PENDING,
                DepositRecord.is_deleted == 0,
            )
            .all()
        )
        stale = [rec for rec in stale if self._is_pending_stale(rec, minutes)]
        for rec in stale:
            rec.status = DepositStatus.UNPAID
        self.db.commit()
        return len(stale)

    def _pending_expire_minutes(self) -> int:
        """F78：废弃 PENDING 押金判定窗口（默认 150 分钟 > 微信支付单有效期约 2 小时）"""
        from backend.common.config_service import ConfigService

        return ConfigService.get_int(self.db, "deposit_pending_expire_minutes", 150)

    def _refund_notify_url(self) -> str:
        """F55：微信退款结果通知 URL（配置 WECHAT_REFUND_NOTIFY_URL）"""
        from backend.config import get_settings

        return getattr(get_settings(), "WECHAT_REFUND_NOTIFY_URL", "")

    def _is_pending_stale(self, record, expire_minutes: int | None = None) -> bool:
        """PENDING 记录是否超过失效窗口（未回调）"""
        minutes = expire_minutes or self._pending_expire_minutes()
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return record.create_time < cutoff

    def get_deposit_status(self, child_id: int) -> dict:
        """查询押金状态"""
        from backend.common.config_service import ConfigService
        from backend.domain.child.models import Child

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        outstanding = str((child.outstanding_fines if child else 0) or 0)

        record = self.deposit_repo.get_active_by_child(child_id)
        if not record:
            amount = ConfigService.get_decimal(
                self.db, "deposit_amount", Decimal("1200")
            )
            return {
                "status": 0,
                "amount": str(amount),
                "fine": outstanding,
                "message": "未缴纳押金",
            }
        return {
            "status": record.status,
            "amount": str(record.amount or 0),
            "paid_at": record.pay_time.isoformat() if record.pay_time else None,
            "fine": outstanding,
        }
