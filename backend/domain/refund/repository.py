# backend/domain/refund/repository.py
"""退款域数据访问层"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.refund.models import RefundApplication


class RefundRepository(BaseRepository[RefundApplication]):
    def __init__(self, db: Session):
        super().__init__(db, RefundApplication)

    def get_by_user(self, user_id: int) -> list[RefundApplication]:
        return (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.user_id == user_id,
                RefundApplication.is_deleted == 0,
            )
            .order_by(RefundApplication.create_time.desc())
            .all()
        )
