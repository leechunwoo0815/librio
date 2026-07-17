# backend/domain/deposit/repository.py
"""押金域数据访问层"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.deposit.models import DepositRecord


class DepositRepository(BaseRepository[DepositRecord]):
    def __init__(self, db: Session):
        super().__init__(db, DepositRecord)

    def get_active_by_child(self, child_id: int) -> DepositRecord | None:
        """获取孩子当前的押金记录（活跃状态：待支付/已支付/退款中/退款待审核）"""
        from backend.common.types import DepositStatus

        return (
            self.db.query(DepositRecord)
            .filter(
                DepositRecord.child_id == child_id,
                DepositRecord.status.in_([
                    DepositStatus.PENDING, DepositStatus.PAID,
                    DepositStatus.REFUNDING, DepositStatus.REFUND_PENDING,
                ]),
                DepositRecord.is_deleted == 0,
            )
            .order_by(DepositRecord.id.desc())
            .first()
        )

    def get_active_by_child_for_update(self, child_id: int) -> DepositRecord | None:
        """获取孩子当前的押金记录（活跃状态），加行锁防止并发"""
        from backend.common.types import DepositStatus

        return (
            self.db.query(DepositRecord)
            .filter(
                DepositRecord.child_id == child_id,
                DepositRecord.status.in_([
                    DepositStatus.PENDING, DepositStatus.PAID,
                    DepositStatus.REFUNDING, DepositStatus.REFUND_PENDING,
                ]),
                DepositRecord.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
