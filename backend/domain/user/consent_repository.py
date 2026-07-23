# backend/domain/user/consent_repository.py
"""同意记录数据访问层"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.user.consent_model import ConsentRecord


class ConsentRepository(BaseRepository[ConsentRecord]):
    """同意记录仓库"""

    def __init__(self, db: Session):
        super().__init__(db, ConsentRecord)

    def get_latest_valid(self, user_id: int, consent_type: str) -> ConsentRecord | None:
        """获取用户指定类型的最新有效同意记录（未撤回）"""
        return (
            self.db.query(ConsentRecord)
            .filter(
                ConsentRecord.user_id == user_id,
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.is_deleted == 0,
                ConsentRecord.withdrawn_at.is_(None),
            )
            .order_by(ConsentRecord.create_time.desc())
            .first()
        )

    def get_all_for_user(self, user_id: int) -> list[ConsentRecord]:
        """获取用户所有同意记录"""
        return (
            self.db.query(ConsentRecord)
            .filter(
                ConsentRecord.user_id == user_id,
                ConsentRecord.is_deleted == 0,
            )
            .order_by(ConsentRecord.create_time.desc())
            .all()
        )
