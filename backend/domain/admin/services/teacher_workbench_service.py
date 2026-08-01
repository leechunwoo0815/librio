# backend/domain/admin/services/teacher_workbench_service.py
"""D1 老师工作台 + D2 老师→家长课后反馈"""

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from backend.common.exceptions import ForbiddenError, NotFoundError
from backend.domain.admin.models import Teacher, TeacherSchedule
from backend.domain.child.models import Child

logger = logging.getLogger(__name__)


class TeacherWorkbenchService:
    """老师工作台聚合服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_workbench(self, teacher_id: int) -> dict:
        """老师首页工作台：今日课程 / 待审核提交 / 负责孩子近况 / 最近指导"""
        from backend.domain.advancement.models import Level, ReadingSubmission
        from backend.domain.evaluation.models import GuidanceRecord
        from backend.domain.book.models import Book

        teacher = (
            self.db.query(Teacher)
            .filter(Teacher.id == teacher_id, Teacher.is_deleted == 0)
            .first()
        )
        if not teacher:
            raise NotFoundError("老师不存在")

        # 今日课程（按星期几匹配排班）
        today_weekday = date.today().isoweekday()
        schedules = (
            self.db.query(TeacherSchedule)
            .filter(
                TeacherSchedule.teacher_id == teacher_id,
                TeacherSchedule.weekday == today_weekday,
                TeacherSchedule.is_deleted == 0,
            )
            .order_by(TeacherSchedule.start_time)
            .all()
        )

        # 负责的孩子
        children = (
            self.db.query(Child)
            .filter(Child.teacher_id == teacher_id, Child.is_deleted == 0)
            .all()
        )
        child_ids = [c.id for c in children]

        # 待审核提交（D4：仅时长不足/未测验的会进入人工队列）
        pending_submissions = []
        if child_ids:
            subs = (
                self.db.query(ReadingSubmission)
                .filter(
                    ReadingSubmission.child_id.in_(child_ids),
                    ReadingSubmission.status == ReadingSubmission.STATUS_PENDING,
                    ReadingSubmission.is_deleted == 0,
                )
                .order_by(ReadingSubmission.create_time)
                .limit(20)
                .all()
            )
            child_map = {c.id: c.name for c in children}
            book_ids = {s.book_id for s in subs}
            books = (
                {
                    b.id: b.title
                    for b in self.db.query(Book).filter(Book.id.in_(book_ids)).all()
                }
                if book_ids
                else {}
            )
            pending_submissions = [
                {
                    "id": s.id,
                    "child_id": s.child_id,
                    "child_name": child_map.get(s.child_id),
                    "book_title": books.get(s.book_id),
                    "submitted_at": s.submitted_at.isoformat()
                    if s.submitted_at
                    else None,
                }
                for s in subs
            ]

        # 孩子近况（级别/累计）
        level_ids = {c.current_level_id for c in children if c.current_level_id}
        levels = (
            {lv.id: lv.name for lv in self.db.query(Level).filter(Level.id.in_(level_ids)).all()}
            if level_ids
            else {}
        )
        children_overview = [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "level_name": levels.get(c.current_level_id),
                "total_books_finished": c.total_books_finished or 0,
                "current_streak_days": c.current_streak_days or 0,
            }
            for c in children
        ]

        # 最近指导记录
        recent_guidance = (
            self.db.query(GuidanceRecord)
            .filter(
                GuidanceRecord.teacher_id == teacher_id,
                GuidanceRecord.is_deleted == 0,
            )
            .order_by(GuidanceRecord.guidance_date.desc())
            .limit(5)
            .all()
        )
        child_name_map = {c.id: c.name for c in children}

        return {
            "teacher": {"id": teacher.id, "name": teacher.name},
            "today_schedules": [
                {
                    "id": s.id,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "course_type": getattr(s, "course_type", None),
                }
                for s in schedules
            ],
            "pending_submissions_count": len(pending_submissions),
            "pending_submissions": pending_submissions,
            "children_count": len(children),
            "children": children_overview,
            "recent_guidance": [
                {
                    "id": g.id,
                    "child_name": child_name_map.get(g.child_id),
                    "content": g.content[:80],
                    "guidance_date": g.guidance_date.isoformat()
                    if g.guidance_date
                    else None,
                }
                for g in recent_guidance
            ],
        }

    def post_feedback(
        self, teacher_id: int, child_id: int, content: str, admin_id: int
    ) -> dict:
        """D2 课后反馈：写指导记录 + 推送给家长（msg_type=4 老师消息）"""
        from backend.domain.evaluation.models import GuidanceRecord
        from backend.domain.message.models import SystemMessage

        teacher = (
            self.db.query(Teacher)
            .filter(Teacher.id == teacher_id, Teacher.is_deleted == 0)
            .first()
        )
        if not teacher:
            raise NotFoundError("老师不存在")

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")
        if child.teacher_id != teacher_id:
            raise ForbiddenError("只能给本人负责的孩子发反馈")

        record = GuidanceRecord(
            child_id=child_id,
            teacher_id=teacher_id,
            content=content,
            guidance_date=datetime.now(),
        )
        self.db.add(record)

        msg = SystemMessage(
            user_id=child.user_id,
            title=f"{teacher.name}老师的课后反馈",
            content=content,
            msg_type=4,  # 老师消息
            priority=1,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(record)

        from backend.domain.admin.services.system_service import AdminSystemService

        AdminSystemService(self.db).write_operation_log(
            admin_id=admin_id,
            module="teacher",
            operation="post_feedback",
            content=f"课后反馈: teacher={teacher_id}, child={child_id}",
        )
        logger.info(f"Teacher feedback: teacher={teacher_id}, child={child_id}")
        return {"success": True, "guidance_id": record.id}
