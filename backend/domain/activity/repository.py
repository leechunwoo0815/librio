# backend/domain/activity/repository.py
"""活动域数据访问层"""

from sqlalchemy.orm import Session
from backend.common.base_repo import BaseRepository
from backend.domain.activity.models import Activity, ActivityEnrollment


class ActivityRepository(BaseRepository[Activity]):
    def __init__(self, db: Session):
        super().__init__(db, Activity)


class ActivityEnrollmentRepository(BaseRepository[ActivityEnrollment]):
    def __init__(self, db: Session):
        super().__init__(db, ActivityEnrollment)

    def count_enrollments(self, activity_id: int) -> int:
        return self.count(activity_id=activity_id)
