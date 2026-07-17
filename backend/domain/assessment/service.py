# backend/domain/assessment/service.py
"""评估域业务逻辑"""

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.domain.assessment.models import Assessment
from backend.domain.assessment.schemas import (
    AssessmentCreateRequest,
    AssessmentUpdateRequest,
    AssessmentResponse,
    AssessmentListResponse,
)
from backend.domain.child.models import Child
from backend.domain.admin.models import Teacher, Venue
from backend.common.exceptions import NotFoundError


class AssessmentService:
    """评估服务"""

    def __init__(self, db: Session):
        self.db = db

    def list_assessments(
        self,
        keyword: str | None = None,
        status: str | None = None,
        venue_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AssessmentListResponse:
        """获取评估列表"""
        query = self.db.query(Assessment).filter(Assessment.is_deleted == 0)

        if status:
            query = query.filter(Assessment.status == status)
        if venue_id:
            query = query.filter(Assessment.venue_id == venue_id)

        # 关键词搜索（按孩子姓名）
        if keyword:
            child_ids = (
                self.db.query(Child.id)
                .filter(Child.name.contains(keyword), Child.is_deleted == 0)
                .all()
            )
            child_ids = [c.id for c in child_ids]
            query = query.filter(Assessment.child_id.in_(child_ids))

        total = query.count()
        items = (
            query.order_by(Assessment.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        result = []
        for a in items:
            child = (
                self.db.query(Child)
                .filter(Child.id == a.child_id, Child.is_deleted == 0)
                .first()
            )
            teacher = (
                self.db.query(Teacher)
                .filter(Teacher.id == a.teacher_id, Teacher.is_deleted == 0)
                .first()
                if a.teacher_id
                else None
            )
            venue = (
                self.db.query(Venue)
                .filter(Venue.id == a.venue_id, Venue.is_deleted == 0)
                .first()
                if a.venue_id
                else None
            )

            ar_change = None
            if a.ar_level_before is not None and a.ar_level_after is not None:
                ar_change = round(a.ar_level_after - a.ar_level_before, 1)

            result.append(
                AssessmentResponse(
                    id=a.id,
                    child_id=a.child_id,
                    child_name=child.name if child else None,
                    teacher_id=a.teacher_id,
                    teacher_name=teacher.name if teacher else None,
                    venue_id=a.venue_id,
                    venue_name=venue.name if venue else None,
                    ar_level_before=a.ar_level_before,
                    ar_level_after=a.ar_level_after,
                    ar_level_change=ar_change,
                    comprehension_score=a.comprehension_score,
                    status=a.status,
                    scheduled_date=a.scheduled_date,
                    completed_date=a.completed_date,
                    notes=a.notes,
                    recommendation=a.recommendation,
                    create_time=a.create_time,
                )
            )

        # 统计数据（使用 SQL 聚合，避免全表加载）
        month_start = datetime.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        # 本月评估数
        month_total = (
            self.db.query(func.count(Assessment.id))
            .filter(Assessment.is_deleted == 0, Assessment.create_time >= month_start)
            .scalar()
            or 0
        )

        # 待评估数
        pending = (
            self.db.query(func.count(Assessment.id))
            .filter(Assessment.is_deleted == 0, Assessment.status == "pending")
            .scalar()
            or 0
        )

        # 平均 AR 变化
        avg_ar_change = (
            self.db.query(
                func.avg(Assessment.ar_level_after - Assessment.ar_level_before)
            )
            .filter(
                Assessment.is_deleted == 0,
                Assessment.ar_level_before.isnot(None),
                Assessment.ar_level_after.isnot(None),
            )
            .scalar()
        )
        avg_ar_change = round(float(avg_ar_change), 1) if avg_ar_change else 0

        # 平均理解正确率
        avg_accuracy = (
            self.db.query(func.avg(Assessment.comprehension_score))
            .filter(
                Assessment.is_deleted == 0, Assessment.comprehension_score.isnot(None)
            )
            .scalar()
        )
        avg_accuracy = round(float(avg_accuracy), 1) if avg_accuracy else 0

        stats = {
            "month_total": month_total,
            "pending": pending,
            "avg_ar_change": avg_ar_change,
            "avg_accuracy": avg_accuracy,
        }

        return AssessmentListResponse(items=result, stats=stats, total=total)

    def get_assessment(self, assessment_id: int) -> AssessmentResponse:
        """获取评估详情"""
        a = (
            self.db.query(Assessment)
            .filter(Assessment.id == assessment_id, Assessment.is_deleted == 0)
            .first()
        )
        if not a:
            raise NotFoundError("评估记录不存在")

        child = (
            self.db.query(Child)
            .filter(Child.id == a.child_id, Child.is_deleted == 0)
            .first()
        )
        teacher = (
            self.db.query(Teacher)
            .filter(Teacher.id == a.teacher_id, Teacher.is_deleted == 0)
            .first()
            if a.teacher_id
            else None
        )
        venue = (
            self.db.query(Venue)
            .filter(Venue.id == a.venue_id, Venue.is_deleted == 0)
            .first()
            if a.venue_id
            else None
        )

        ar_change = None
        if a.ar_level_before is not None and a.ar_level_after is not None:
            ar_change = round(a.ar_level_after - a.ar_level_before, 1)

        return AssessmentResponse(
            id=a.id,
            child_id=a.child_id,
            child_name=child.name if child else None,
            teacher_id=a.teacher_id,
            teacher_name=teacher.name if teacher else None,
            venue_id=a.venue_id,
            venue_name=venue.name if venue else None,
            ar_level_before=a.ar_level_before,
            ar_level_after=a.ar_level_after,
            ar_level_change=ar_change,
            comprehension_score=a.comprehension_score,
            status=a.status,
            scheduled_date=a.scheduled_date,
            completed_date=a.completed_date,
            notes=a.notes,
            recommendation=a.recommendation,
            create_time=a.create_time,
        )

    def create_assessment(self, data: AssessmentCreateRequest) -> AssessmentResponse:
        """创建评估"""
        # 验证孩子存在
        child = (
            self.db.query(Child)
            .filter(Child.id == data.child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")

        assessment = Assessment(
            child_id=data.child_id,
            teacher_id=data.teacher_id,
            venue_id=data.venue_id,
            ar_level_before=data.ar_level_before,
            ar_level_after=data.ar_level_after,
            comprehension_score=data.comprehension_score,
            status=data.status,
            scheduled_date=data.scheduled_date,
            notes=data.notes,
            recommendation=data.recommendation,
        )
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)

        return self.get_assessment(assessment.id)

    def update_assessment(
        self, assessment_id: int, data: AssessmentUpdateRequest
    ) -> AssessmentResponse:
        """更新评估"""
        assessment = (
            self.db.query(Assessment)
            .filter(Assessment.id == assessment_id, Assessment.is_deleted == 0)
            .first()
        )
        if not assessment:
            raise NotFoundError("评估记录不存在")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(assessment, key):
                setattr(assessment, key, value)

        # 如果状态改为 completed，自动设置完成时间
        if data.status == "completed" and not assessment.completed_date:
            assessment.completed_date = datetime.now()

        self.db.commit()
        return self.get_assessment(assessment_id)

    def delete_assessment(self, assessment_id: int) -> dict:
        """删除评估"""
        assessment = (
            self.db.query(Assessment)
            .filter(Assessment.id == assessment_id, Assessment.is_deleted == 0)
            .first()
        )
        if not assessment:
            raise NotFoundError("评估记录不存在")

        assessment.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "评估记录已删除"}
