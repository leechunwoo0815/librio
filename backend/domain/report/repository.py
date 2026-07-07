# backend/domain/report/repository.py
"""报告域数据访问层"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.report.models import ObservationReport, LearningReport


class ObservationReportRepository(BaseRepository[ObservationReport]):
    def __init__(self, db: Session):
        super().__init__(db, ObservationReport)


class LearningReportRepository(BaseRepository[LearningReport]):
    def __init__(self, db: Session):
        super().__init__(db, LearningReport)
