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
