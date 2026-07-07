# backend/domain/admin/repository.py
"""管理域数据访问层"""

from sqlalchemy.orm import Session
from backend.common.base_repo import BaseRepository
from backend.domain.admin.models import (
    Admin,
    OperationLog,
    SystemConfig,
    Teacher,
    TeacherSchedule,
    Venue,
)


class AdminRepository(BaseRepository[Admin]):
    def __init__(self, db: Session):
        super().__init__(db, Admin)


class OperationLogRepository(BaseRepository[OperationLog]):
    def __init__(self, db: Session):
        super().__init__(db, OperationLog)


class SystemConfigRepository(BaseRepository[SystemConfig]):
    def __init__(self, db: Session):
        super().__init__(db, SystemConfig)

    def get_by_key(self, key: str) -> SystemConfig | None:
        return self.get_by_field("config_key", key)

    def get_all_configs(self) -> list[SystemConfig]:
        """获取所有配置项"""
        return self.db.query(SystemConfig).filter(SystemConfig.is_deleted == 0).all()


class TeacherRepository(BaseRepository[Teacher]):
    def __init__(self, db: Session):
        super().__init__(db, Teacher)


class TeacherScheduleRepository(BaseRepository[TeacherSchedule]):
    def __init__(self, db: Session):
        super().__init__(db, TeacherSchedule)

    def get_by_teacher(self, teacher_id: int) -> list[TeacherSchedule]:
        """获取老师排班列表"""
        return (
            self.db.query(TeacherSchedule)
            .filter(
                TeacherSchedule.teacher_id == teacher_id,
                TeacherSchedule.is_deleted == 0,
            )
            .order_by(TeacherSchedule.weekday)
            .all()
        )


class VenueRepository(BaseRepository[Venue]):
    def __init__(self, db: Session):
        super().__init__(db, Venue)
