# backend/domain/deposit/service.py
"""押金域业务逻辑 — V3.1 状态机管理

UNPAID → PAID → REFUNDED / DEDUCTED
       → PENDING → PAID (真实网关路径)
"""

import logging
import uuid
from datetime import datetime
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
from backend.common.gateways.payment import (
    PaymentGateway,
    PaymentOrderRequest,
    PaymentRefundRequest,
)
from backend.common.types import BorrowStatus, DepositStatus
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
        """缴纳押金 — 必须经过支付网关"""
        existing = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if existing:
            raise ConflictError("押金已缴纳")

        from backend.common.config_service import ConfigService

        deposit_amount = ConfigService.get_decimal(
            self.db, "deposit_amount", DEFAULT_DEPOSIT_AMOUNT
        )

        from backend.domain.user.models import User

        user = self.db.query(User).filter(User.id == current_user.id).first()
        if not user or not user.openid:
            raise ValidationError("用户openid不存在")

        order_no = self._generate_order_no()
        amount_cent = int(deposit_amount * 100)

        openid = user.openid
        order_req = PaymentOrderRequest(
            out_trade_no=order_no,
            amount=amount_cent,
            description="押金",
            openid=openid,
            attach="deposit",
        )
        result = await payment_gateway.create_order(order_req)
        if not result.success:
            raise PaymentError(result.error_message)

        is_instant = payment_gateway.supports_instant_payment
        status = DepositStatus.PAID if is_instant else DepositStatus.PENDING
        pay_time = datetime.now() if is_instant else None

        record = DepositRecord(
            child_id=data.child_id,
            amount=deposit_amount,
            status=status,
            pay_time=pay_time,
            pay_order_id=order_no,
        )
        created = self.deposit_repo.create(record)

        if is_instant:
            event_bus.publish(
                DepositPaidEvent(
                    child_id=data.child_id,
                    deposit_id=created.id,
                    amount=deposit_amount,
                ),
                db=self.db,
            )

        self.db.commit()
        return DepositPayResponse(
            deposit=DepositResponse.model_validate(created),
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
        """重新缴纳押金（DEDUCTED/REFUNDED → PAID），必须经过支付网关"""
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

        from backend.common.config_service import ConfigService

        deposit_amount = ConfigService.get_decimal(
            self.db, "deposit_amount", DEFAULT_DEPOSIT_AMOUNT
        )

        from backend.domain.user.models import User

        user = self.db.query(User).filter(User.id == child.user_id).first()
        if not user or not user.openid:
            raise ValidationError("用户openid不存在")

        order_no = self._generate_order_no()
        amount_cent = int(deposit_amount * 100)

        order_req = PaymentOrderRequest(
            out_trade_no=order_no,
            amount=amount_cent,
            description="押金（重新缴纳）",
            openid=user.openid,
            attach="deposit",
        )
        result = await payment_gateway.create_order(order_req)
        if not result.success:
            raise PaymentError(result.error_message)

        is_instant = payment_gateway.supports_instant_payment
        status = DepositStatus.PAID if is_instant else DepositStatus.PENDING
        pay_time = datetime.now() if is_instant else None

        record = DepositRecord(
            child_id=child_id,
            amount=deposit_amount,
            status=status,
            pay_time=pay_time,
            pay_order_id=order_no,
        )
        created = self.deposit_repo.create(record)

        child.deposit_status = status

        if is_instant:
            event_bus.publish(
                DepositPaidEvent(
                    child_id=child_id,
                    deposit_id=created.id,
                    amount=deposit_amount,
                ),
                db=self.db,
            )

        self.db.commit()
        return DepositPayResponse(
            deposit=DepositResponse.model_validate(created),
            pay_params=result.pay_params,
        )

    def refund_deposit(self, data: DepositRefundRequest) -> DepositResponse:
        """申请退还押金 — 进入 REFUND_PENDING 等待管理员审核"""
        record = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")

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
        if child and child.outstanding_fines and child.outstanding_fines > 0:
            raise ValidationError(f"请先结清未缴罚款 {child.outstanding_fines} 元")

        record.status = DepositStatus.REFUND_PENDING
        self.deposit_repo.update(record)

        if child:
            child.deposit_status = DepositStatus.REFUND_PENDING

        self.db.commit()
        logger.info(
            f"Refund requested: child_id={data.child_id}, status=REFUND_PENDING"
        )
        return DepositResponse.model_validate(record)

    def deduct_deposit(self, data: DepositDeductRequest) -> DepositResponse:
        """扣除押金 — 仅允许 PAID 状态下扣除"""
        record = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")
        if record.status != DepositStatus.PAID:
            raise ConflictError(f"当前状态({record.status})不允许扣除，仅 PAID 可扣除")

        if data.amount > record.amount:
            raise ValidationError("扣除金额超过押金余额")

        record.status = DepositStatus.DEDUCTED
        record.deduct_amount = data.amount
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
            child.outstanding_fines = (child.outstanding_fines or 0) + data.amount

        self.db.commit()
        return DepositResponse.model_validate(record)

    def mark_book_lost(self, borrow_record_id: int, admin_id: int) -> dict:
        """图书丢失登记 — 更新借阅状态 + 计算罚款"""
        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus
        from backend.common.config_service import ConfigService
        from backend.domain.book.models import Book

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

        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .first()
        )
        if child:
            child.outstanding_fines = (child.outstanding_fines or 0) + fine_amount

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
        """审核押金退款 — approve 触发真实退款，reject 回退 PAID"""
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

        if action == "approve":
            active_borrows = (
                self.db.query(BorrowRecord)
                .filter(
                    BorrowRecord.child_id == child_id,
                    BorrowRecord.status.in_(
                        [BorrowStatus.BORROWING, BorrowStatus.OVERDUE]
                    ),
                    BorrowRecord.is_deleted == 0,
                )
                .with_for_update()
                .count()
            )
            if active_borrows > 0:
                raise ValidationError(
                    f"该孩子有 {active_borrows} 本未还书，请先归还再退款"
                )

            record.status = DepositStatus.REFUNDING
            record.refund_time = datetime.now()
            record.refund_amount = record.amount
            if child:
                child.deposit_status = DepositStatus.REFUNDING

            if payment_gateway:
                try:
                    result = await payment_gateway.refund(
                        PaymentRefundRequest(
                            out_trade_no=str(record.pay_order_id)
                            if record.pay_order_id
                            else "",
                            total_amount=record.amount,
                            refund_amount=record.amount,
                            reason="押金退款（审核通过）",
                        )
                    )
                    if hasattr(result, "success") and not result.success:
                        raise PaymentError(
                            getattr(result, "error_message", "退款接口返回失败")
                        )
                except Exception as e:
                    self.db.rollback()
                    logger.error(
                        f"Refund failed, transaction rolled back: child={child_id}, error={e}"
                    )
                    raise PaymentError(f"押金退款调用失败: {e}")

        elif action == "reject":
            record.status = DepositStatus.PAID
            record.refund_time = None
            record.refund_amount = None
            if child:
                child.deposit_status = DepositStatus.PAID
        else:
            raise ValidationError(f"未知审核动作: {action}，仅支持 approve/reject")

        self.deposit_repo.update(record)
        self.db.commit()

        from backend.domain.admin.services.system_service import AdminSystemService

        system_service = AdminSystemService(self.db)
        system_service.write_operation_log(
            admin_id=admin_id,
            module="deposit",
            operation=f"refund_{action}",
            content=f"押金退款审核 [{action}]: 孩子 #{child_id}",
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
        """标记押金已到账退款 — REFUNDING → REFUNDED"""
        record = self.deposit_repo.get_active_by_child_for_update(child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")
        if record.status != DepositStatus.REFUNDING:
            raise ConflictError("当前状态不是退款中，无法标记到账")

        record.status = DepositStatus.REFUNDED
        record.refund_time = record.refund_time or datetime.now()
        record.refund_amount = record.refund_amount or record.amount

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child:
            child.deposit_status = DepositStatus.REFUNDED

        self.db.commit()
        return DepositResponse.model_validate(record)

    def get_deposit_status(self, child_id: int) -> dict:
        """查询押金状态"""
        record = self.deposit_repo.get_active_by_child(child_id)
        if not record:
            return {"status": 0, "amount": 0, "message": "未缴纳押金"}
        return {
            "status": record.status,
            "amount": str(record.amount or 0),
            "paid_at": record.pay_time.isoformat() if record.pay_time else None,
        }
