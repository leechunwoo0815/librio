# backend/domain/refund/repository.py
"""退款域数据访问层"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.refund.models import RefundApplication


class RefundRepository(BaseRepository[RefundApplication]):
    def __init__(self, db: Session):
        super().__init__(db, RefundApplication)

    def get_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[RefundApplication], int]:
        q = self.db.query(RefundApplication).filter(
            RefundApplication.user_id == user_id,
            RefundApplication.is_deleted == 0,
        )
        total = q.count()
        records = (
            q.order_by(RefundApplication.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return records, total
