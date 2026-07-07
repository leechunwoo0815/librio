# backend/domain/reservation/service.py
"""预约域业务逻辑 — V3.1 预约借书

预约 → 锁定库存 → 72h内取书 → 转为借阅
过期 → 释放库存
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.events import (
    ReservationCreatedEvent,
    ReservationFulfilledEvent,
    ReservationExpiredEvent,
    event_bus,
)
from backend.common.exceptions import ConflictError, ValidationError
from backend.common.types import ReservationStatus
from backend.domain.book.models import Book
from backend.domain.reservation.models import Reservation
from backend.domain.reservation.repository import ReservationRepository
from backend.domain.reservation.schemas import (
    ReservationCreateRequest,
    ReservationFulfillRequest,
    ReservationResponse,
)

logger = logging.getLogger(__name__)

RESERVATION_HOURS = (
    72  # 默认值，通过 ConfigService.get_int(db, "reservation_expire_hours", 72) 读取
)


class ReservationService:
    """预约服务"""

    def __init__(self, db: Session):
        self.db = db
        self.reservation_repo = ReservationRepository(db)
        self.book_repo = BaseRepository(db, Book)

    def create_reservation(self, data: ReservationCreateRequest) -> ReservationResponse:
        """创建预约 — 锁定库存"""
        book = self.book_repo.get_by_id_or_raise(data.book_id)
        if not book.offline_available:
            raise ValidationError("该书不支持线下借阅")
        if (book.available_stock or 0) <= 0:
            raise ValidationError("库存不足，无法预约")

        # 重复预约校验
        from backend.common.types import ReservationStatus

        existing = (
            self.db.query(Reservation)
            .filter(
                Reservation.child_id == data.child_id,
                Reservation.book_id == data.book_id,
                Reservation.status == ReservationStatus.PENDING,
                Reservation.is_deleted == 0,
            )
            .first()
        )
        if existing:
            raise ConflictError("该孩子已预约同一本书，请等待取书或取消后再预约")

        # 从配置读取预约过期时间
        from backend.common.config_service import ConfigService

        expire_hours = ConfigService.get_int(
            self.db, "reservation_expire_hours", RESERVATION_HOURS
        )

        reservation = Reservation(
            child_id=data.child_id,
            book_id=data.book_id,
            venue_id=data.venue_id,
            status=ReservationStatus.PENDING,
            expire_time=datetime.now() + timedelta(hours=expire_hours),
        )
        created = self.reservation_repo.create(reservation)

        # 发布预约创建事件（book 域扣库存）
        event_bus.publish(
            ReservationCreatedEvent(
                child_id=data.child_id,
                book_id=data.book_id,
                reservation_id=created.id,
            ),
            db=self.db,
        )

        self.db.commit()
        return ReservationResponse.model_validate(created)

    def fulfill_reservation(
        self, data: ReservationFulfillRequest
    ) -> ReservationResponse:
        """取书 — 转为正式借阅"""
        reservation = self.reservation_repo.get_by_id_or_raise(data.reservation_id)
        if reservation.status != ReservationStatus.PENDING:
            raise ConflictError("预约状态不正确")

        if datetime.now() > reservation.expire_time:
            raise ValidationError("预约已过期")

        # 校验借阅上限
        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus
        from backend.common.config_service import ConfigService

        max_borrow = ConfigService.get_int(self.db, "borrow_limit", 20)
        active_count = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == reservation.child_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )
        if active_count >= max_borrow:
            raise ValidationError(f"借阅上限 {max_borrow} 本，请先归还")

        reservation.status = ReservationStatus.FULFILLED
        reservation.fulfilled_time = datetime.now()
        self.reservation_repo.update(reservation)

        # 发布取书事件（borrow 域创建借阅记录）
        event_bus.publish(
            ReservationFulfilledEvent(
                child_id=reservation.child_id,
                book_id=reservation.book_id,
                reservation_id=reservation.id,
            ),
            db=self.db,
        )

        self.db.commit()
        return ReservationResponse.model_validate(reservation)

    def expire_reservation(self, reservation_id: int) -> None:
        """过期预约 — 释放库存（定时任务调用，不自行 commit）"""
        reservation = self.reservation_repo.get_by_id(reservation_id)
        if not reservation or reservation.status != ReservationStatus.PENDING:
            return

        reservation.status = ReservationStatus.EXPIRED
        self.reservation_repo.update(reservation)

        event_bus.publish(
            ReservationExpiredEvent(
                child_id=reservation.child_id,
                book_id=reservation.book_id,
                reservation_id=reservation.id,
            ),
            db=self.db,
        )

    def get_child_reservations(self, child_id: int) -> list[ReservationResponse]:
        records = self.reservation_repo.get_active_by_child(child_id)
        return [ReservationResponse.model_validate(r) for r in records]

    def cancel_reservation(self, reservation_id: int) -> dict:
        """取消预约"""
        from backend.common.exceptions import NotFoundError
        record = self.reservation_repo.get_by_id(reservation_id)
        if not record or record.is_deleted == 1:
            raise NotFoundError("预约不存在")
        if record.status == 3:  # 已取消
            raise ConflictError("预约已取消")
        record.status = 3  # Cancelled
        self.reservation_repo.update(record)
        self.db.commit()
        return {"success": True, "message": "预约已取消"}
