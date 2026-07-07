# backend/domain/reservation/repository.py
"""预约域数据访问层"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.types import ReservationStatus
from backend.domain.reservation.models import Reservation


class ReservationRepository(BaseRepository[Reservation]):
    def __init__(self, db: Session):
        super().__init__(db, Reservation)

    def get_active_by_child(self, child_id: int) -> list[Reservation]:
        return self.list_all(
            limit=50, child_id=child_id, status=ReservationStatus.PENDING
        )

    def get_expired_pending(self) -> list[Reservation]:
        """获取所有已过期但仍为 PENDING 状态的预约"""
        from datetime import datetime

        return (
            self.db.query(Reservation)
            .filter(
                Reservation.status == ReservationStatus.PENDING,
                Reservation.expire_time < datetime.now(),
                Reservation.is_deleted == 0,
            )
            .all()
        )
