# backend/domain/certificate/repository.py
"""证书域数据访问层"""

from sqlalchemy.orm import Session
from backend.common.base_repo import BaseRepository
from backend.domain.certificate.models import LevelCertificate


class CertificateRepository(BaseRepository[LevelCertificate]):
    def __init__(self, db: Session):
        super().__init__(db, LevelCertificate)

    def get_by_child(self, child_id: int) -> list[LevelCertificate]:
        return self.list_all(limit=50, child_id=child_id)

    def get_by_child_and_level(self, child_id: int, level_id: int):
        return (
            self.db.query(LevelCertificate)
            .filter(
                LevelCertificate.child_id == child_id,
                LevelCertificate.level_id == level_id,
            )
            .first()
        )
