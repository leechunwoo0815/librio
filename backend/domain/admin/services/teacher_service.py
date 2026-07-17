# backend/domain/admin/services/teacher_service.py
"""老师管理 Service — 从 AdminService 拆分出来的独立域服务。"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.exceptions import NotFoundError
from backend.domain.admin.models import Teacher, TeacherSchedule, Venue
from backend.domain.admin.repository import TeacherRepository, TeacherScheduleRepository
from backend.domain.admin.schemas import (
    SuccessResponse,
    TeacherResponse,
    TeacherScheduleResponse,
    UpdateTeacherRequest,
)
from backend.domain.child.models import Child

logger = logging.getLogger(__name__)


class AdminTeacherService:
    """老师管理：负责老师 CRUD、孩子分配、排班管理。"""

    def __init__(self, db: Session):
        self.db = db
        self.teacher_repo = TeacherRepository(db)
        self.schedule_repo = TeacherScheduleRepository(db)
        self.child_repo = BaseRepository(db, Child)

    def list_teachers(self, page: int = 1, page_size: int = 100) -> dict:
        offset = (page - 1) * page_size
        items = self.teacher_repo.list_all(limit=page_size, offset=offset)
        total = self.teacher_repo.count()

        # 预加载场馆名与每个老师负责的孩子数
        venues = {
            v.id: v.name
            for v in self.db.query(Venue).filter(Venue.is_deleted == 0).all()
        }
        student_counts = {
            row.teacher_id: row.cnt
            for row in self.db.query(
                Child.teacher_id, func.count(Child.id).label("cnt")
            )
            .filter(Child.is_deleted == 0, Child.teacher_id.isnot(None))
            .group_by(Child.teacher_id)
            .all()
        }

        # 预加载每个 teacher_id 对应的管理员账号
        from backend.domain.admin.models import Admin

        admin_map = {}
        admins = (
            self.db.query(Admin)
            .filter(
                Admin.teacher_id.isnot(None),
                Admin.is_deleted == 0,
            )
            .all()
        )
        for a in admins:
            role_name = a.role_ref.name if a.role_ref else "未知"
            admin_map[a.teacher_id] = {"admin_id": a.id, "admin_role_name": role_name}

        enriched = []
        for t in items:
            admin_info = admin_map.get(t.id, {})
            data = {
                **TeacherResponse.model_validate(t).model_dump(),
                "venue_name": venues.get(t.venue_id),
                "student_count": student_counts.get(t.id, 0),
                "admin_id": admin_info.get("admin_id"),
                "admin_role_name": admin_info.get("admin_role_name"),
            }
            enriched.append(TeacherResponse.model_validate(data))

        return {
            "items": enriched,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
        }

    def get_teacher_by_id(self, teacher_id: int) -> TeacherResponse | None:
        teacher = self.teacher_repo.get_by_id(teacher_id)
        return TeacherResponse.model_validate(teacher) if teacher else None

    def create_teacher(
        self,
        name: str,
        phone: str,
        venue_id: int,
        english_name: str | None = None,
        title: str | None = None,
        introduction: str | None = None,
        expertise: str | None = None,
        status: str | None = "online",
    ) -> TeacherResponse:
        """创建老师"""
        teacher = Teacher(
            name=name,
            english_name=english_name,
            phone=phone,
            venue_id=venue_id,
            title=title,
            introduction=introduction,
            expertise=expertise,
            status=status or "online",
        )
        created = self.teacher_repo.create(teacher)
        self.db.commit()
        logger.info(f"Teacher created: {teacher.name} (id={created.id})")
        return TeacherResponse.model_validate(created)

    def update_teacher(self, teacher_id: int, data: UpdateTeacherRequest) -> dict:
        """更新老师"""
        teacher = self.teacher_repo.get_by_id(teacher_id)
        if not teacher or teacher.is_deleted == 1:
            raise NotFoundError("老师不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(teacher, key):
                setattr(teacher, key, value)
        self.teacher_repo.update(teacher)
        self.db.commit()
        return {"success": True, "message": "老师更新成功"}

    def delete_teacher(self, teacher_id: int) -> dict:
        """删除老师"""
        teacher = self.teacher_repo.get_by_id(teacher_id)
        if not teacher or teacher.is_deleted == 1:
            raise NotFoundError("老师不存在")
        self.teacher_repo.soft_delete(teacher_id)
        self.db.commit()
        return {"success": True, "message": "老师已删除"}

    def assign_teacher(self, child_id: int, teacher_id: int):
        """分配老师给孩子"""
        teacher = self.teacher_repo.get_by_id(teacher_id)
        if not teacher:
            raise NotFoundError("老师不存在")

        child = self.child_repo.get_by_id(child_id)
        if not child:
            raise NotFoundError("孩子不存在")

        child.teacher_id = teacher_id
        self.db.commit()
        logger.info(f"Teacher {teacher_id} assigned to child {child_id}")
        return True

    def get_teacher_children(self, teacher_id: int) -> list:
        """获取老师负责的孩子列表"""
        return (
            self.db.query(Child)
            .filter(
                Child.teacher_id == teacher_id,
                Child.is_deleted == 0,
            )
            .all()
        )

    def get_all_teachers(self) -> list[TeacherResponse]:
        """获取所有老师"""
        return [
            TeacherResponse.model_validate(t)
            for t in self.teacher_repo.list_all(limit=100)
        ]

    def get_child_teacher(self, child_id: int) -> TeacherResponse | None:
        """获取孩子的老师"""
        child = self.child_repo.get_by_id(child_id)
        if not child or not child.teacher_id:
            return None
        return self.get_teacher_by_id(child.teacher_id)

    # ==================== 排班管理 ====================

    def create_schedule(
        self,
        teacher_id: int,
        weekday: int,
        start_time: str,
        end_time: str,
    ) -> TeacherScheduleResponse:
        """创建排班"""
        teacher = self.teacher_repo.get_by_id(teacher_id)
        if not teacher:
            raise NotFoundError("老师不存在")
        schedule = TeacherSchedule(
            teacher_id=teacher_id,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
        )
        created = self.schedule_repo.create(schedule)
        self.db.commit()
        return TeacherScheduleResponse.model_validate(created)

    def get_teacher_schedule(self, teacher_id: int) -> list[TeacherScheduleResponse]:
        """获取老师排班列表"""
        schedules = self.schedule_repo.get_by_teacher(teacher_id)
        return [TeacherScheduleResponse.model_validate(s) for s in schedules]

    def delete_schedule(self, schedule_id: int) -> SuccessResponse:
        """删除排班"""
        schedule = self.schedule_repo.get_by_id(schedule_id)
        if not schedule:
            raise NotFoundError("排班不存在")
        self.schedule_repo.soft_delete(schedule_id)
        self.db.commit()
        return SuccessResponse(success=True)
