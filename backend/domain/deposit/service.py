# backend/domain/deposit/service.py
"""押金域业务逻辑 — V3.1 状态机管理

UNPAID → PAID → REFUNDED / DEDUCTED
"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.common.events import DepositPaidEvent, event_bus
from backend.common.exceptions import ConflictError, NotFoundError, ValidationError
from backend.common.types import BorrowStatus, DepositStatus
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.deposit.repository import DepositRepository
from backend.domain.deposit.schemas import (
    DepositPayRequest,
    DepositRefundRequest,
    DepositDeductRequest,
    DepositResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_DEPOSIT_AMOUNT = Decimal(
    "1200.00"
)  # 默认值，通过 ConfigService.get_decimal(db, "deposit_amount", ...) 读取


class DepositService:
    """押金服务 — 状态机管理"""

    def __init__(self, db: Session):
        self.db = db
        self.deposit_repo = DepositRepository(db)

    def pay_deposit(self, data: DepositPayRequest) -> DepositResponse:
        """缴纳押金"""
        # 检查是否已缴纳（加行锁防并发）
        existing = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if existing:
            raise ConflictError("押金已缴纳")

        # 从配置读取押金金额
        from backend.common.config_service import ConfigService

        deposit_amount = ConfigService.get_decimal(
            self.db, "deposit_amount", DEFAULT_DEPOSIT_AMOUNT
        )

        record = DepositRecord(
            child_id=data.child_id,
            amount=deposit_amount,
            status=DepositStatus.PAID,
            pay_time=datetime.now(),
        )
        created = self.deposit_repo.create(record)

        # 发布押金支付事件
        event_bus.publish(
            DepositPaidEvent(
                child_id=data.child_id,
                deposit_id=created.id,
                amount=deposit_amount,
            ),
            db=self.db,
        )

        self.db.commit()
        return DepositResponse.model_validate(created)

    def refund_deposit(self, data: DepositRefundRequest) -> DepositResponse:
        """退还押金 — 需校验无未还书 + 无未缴罚款"""
        record = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")

        # 校验无活跃借阅记录
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

        # 校验无未缴罚款
        child = (
            self.db.query(Child)
            .filter(Child.id == data.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if child and child.outstanding_fines and child.outstanding_fines > 0:
            raise ValidationError(f"请先结清未缴罚款 {child.outstanding_fines} 元")

        record.status = DepositStatus.REFUNDING
        record.refund_time = datetime.now()
        record.refund_amount = record.amount
        self.deposit_repo.update(record)

        # 同步更新孩子状态
        if child:
            child.deposit_status = DepositStatus.REFUNDING

        self.db.commit()
        return DepositResponse.model_validate(record)

    def deduct_deposit(self, data: DepositDeductRequest) -> DepositResponse:
        """扣除押金 — 图书丢失/严重损坏"""
        record = self.deposit_repo.get_active_by_child_for_update(data.child_id)
        if not record:
            raise NotFoundError("未找到已缴纳的押金记录")

        if data.amount > record.amount:
            raise ValidationError("扣除金额超过押金余额")

        record.status = DepositStatus.DEDUCTED
        record.deduct_amount = data.amount
        record.deduct_reason = data.reason
        self.deposit_repo.update(record)

        # 同步更新孩子状态
        child = (
            self.db.query(Child)
            .filter(Child.id == data.child_id, Child.is_deleted == 0)
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
            .first()
        )
        if not record:
            raise NotFoundError("借阅记录不存在")
        if record.status not in (BorrowStatus.BORROWING, BorrowStatus.OVERDUE):
            raise ValidationError(f"当前状态({record.status})不允许标记丢失")

        # 从配置读取丢书罚款倍率
        multiplier = ConfigService.get_decimal(
            self.db, "lost_book_fine_multiplier", Decimal("1.5")
        )
        book = self.db.query(Book).filter(Book.id == record.book_id).first()
        book_price = book.price if book and book.price else Decimal("0")
        fine_amount = book_price * multiplier

        # 更新借阅记录
        record.status = BorrowStatus.LOST
        record.fine_amount = fine_amount

        # 更新孩子罚款余额
        child = (
            self.db.query(Child)
            .filter(Child.id == record.child_id, Child.is_deleted == 0)
            .first()
        )
        if child:
            child.outstanding_fines = (child.outstanding_fines or 0) + fine_amount

        # 丢书不恢复库存（实体书已丢失），但总库存 -1
        if book:
            book.total_stock = max((book.total_stock or 0) - 1, 0)

        self.db.commit()
        logger.info(
            f"Book lost: borrow_id={borrow_record_id}, fine={fine_amount}, admin_id={admin_id}"
        )
        return {
            "success": True,
            "borrow_record_id": borrow_record_id,
            "fine_amount": str(fine_amount),
        }

    def repay_deposit(self, child_id: int) -> DepositResponse:
        """重新缴纳押金（DEDUCTED/REFUNDED → PAID）"""
        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")

        existing = self.deposit_repo.get_active_by_child(child_id)
        if existing and existing.status == DepositStatus.PAID:
            raise ConflictError("押金已缴纳，无需重复缴纳")

        from backend.common.config_service import ConfigService

        deposit_amount = ConfigService.get_decimal(
            self.db, "deposit_amount", DEFAULT_DEPOSIT_AMOUNT
        )

        record = DepositRecord(
            child_id=child_id,
            amount=deposit_amount,
            status=DepositStatus.PAID,
            pay_time=datetime.now(),
        )
        created = self.deposit_repo.create(record)

        child.deposit_status = DepositStatus.PAID

        event_bus.publish(
            DepositPaidEvent(
                child_id=child_id,
                deposit_id=created.id,
                amount=deposit_amount,
            ),
            db=self.db,
        )

        self.db.commit()
        return DepositResponse.model_validate(created)

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
