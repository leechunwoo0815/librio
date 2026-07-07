# backend/domain/assessment/schemas.py
"""评估域 Pydantic 模型"""

from datetime import datetime
from backend.common.base_schema import BaseSchema


class AssessmentResponse(BaseSchema):
    """评估响应"""
    id: int
    child_id: int
    child_name: str | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None
    venue_id: int | None = None
    venue_name: str | None = None
    ar_level_before: float | None = None
    ar_level_after: float | None = None
    ar_level_change: float | None = None
    comprehension_score: float | None = None
    status: str = "pending"
    scheduled_date: datetime | None = None
    completed_date: datetime | None = None
    notes: str | None = None
    recommendation: str | None = None
    create_time: datetime | None = None


class AssessmentCreateRequest(BaseSchema):
    """创建评估请求"""
    child_id: int
    teacher_id: int | None = None
    venue_id: int | None = None
    ar_level_before: float | None = None
    ar_level_after: float | None = None
    comprehension_score: float | None = None
    status: str = "pending"
    scheduled_date: datetime | None = None
    notes: str | None = None
    recommendation: str | None = None


class AssessmentUpdateRequest(BaseSchema):
    """更新评估请求"""
    ar_level_before: float | None = None
    ar_level_after: float | None = None
    comprehension_score: float | None = None
    status: str | None = None
    scheduled_date: datetime | None = None
    completed_date: datetime | None = None
    notes: str | None = None
    recommendation: str | None = None


class AssessmentListResponse(BaseSchema):
    """评估列表响应"""
    items: list[AssessmentResponse]
    stats: dict
    total: int
