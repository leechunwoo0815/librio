# backend/domain/parent_course_time/service.py
"""亲子课时间段业务逻辑"""

import logging

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.parent_course_time.models import ParentCourseTime
from backend.domain.parent_course_time.schemas import (
    ParentCourseTimeCreate,
    ParentCourseTimeResponse,
    ParentCourseTimeUpdate,
)

logger = logging.getLogger(__name__)


class ParentCourseTimeService:
    """亲子课时间段服务"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = BaseRepository(db, ParentCourseTime)

    def list_by_venue(self, venue_id: int) -> list[ParentCourseTimeResponse]:
        """用户端 — 列出场馆可选时间段"""
        records = (
            self.db.query(ParentCourseTime)
            .filter(
                ParentCourseTime.venue_id == venue_id,
                ParentCourseTime.status == 1,  # 仅可预约
                ParentCourseTime.is_deleted == 0,
            )
            .order_by(ParentCourseTime.course_date, ParentCourseTime.start_time)
            .all()
        )
        return [ParentCourseTimeResponse.model_validate(r) for r in records]

    def list_all(self, venue_id: int | None = None) -> list[ParentCourseTimeResponse]:
        """管理端 — 列出所有时间段"""
        q = self.db.query(ParentCourseTime).filter(
            ParentCourseTime.is_deleted == 0,
        )
        if venue_id is not None:
            q = q.filter(ParentCourseTime.venue_id == venue_id)
        records = q.order_by(
            ParentCourseTime.course_date.desc(), ParentCourseTime.start_time
        ).all()
        return [ParentCourseTimeResponse.model_validate(r) for r in records]

    def create(self, data: ParentCourseTimeCreate) -> ParentCourseTimeResponse:
        """创建时间段"""
        record = ParentCourseTime(
            venue_id=data.venue_id,
            course_date=data.course_date,
            start_time=data.start_time,
            end_time=data.end_time,
            max_participants=data.max_participants,
        )
        created = self.repo.create(record)
        self.db.commit()
        logger.info(
            f"ParentCourseTime created: id={created.id}, venue={data.venue_id}, "
            f"date={data.course_date}"
        )
        return ParentCourseTimeResponse.model_validate(created)

    def update(
        self, slot_id: int, data: ParentCourseTimeUpdate
    ) -> ParentCourseTimeResponse:
        """更新时间段"""
        record = self.repo.get_by_id_or_raise(slot_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(record, key, value)
        self.repo.update(record)
        self.db.commit()
        return ParentCourseTimeResponse.model_validate(record)

    def delete(self, slot_id: int) -> dict:
        """删除时间段（软删除）"""
        record = self.repo.get_by_id_or_raise(slot_id)
        record.is_deleted = 1
        self.repo.update(record)
        self.db.commit()
        logger.info(f"ParentCourseTime deleted: id={slot_id}")
        return {"success": True, "id": slot_id}

    def get(self, slot_id: int) -> ParentCourseTimeResponse:
        """获取单个时间段"""
        record = self.repo.get_by_id_or_raise(slot_id)
        return ParentCourseTimeResponse.model_validate(record)
