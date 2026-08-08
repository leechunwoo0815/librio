# backend/domain/assessment/schemas.py
"""评估域 Pydantic 模型"""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from backend.common.base_schema import BaseSchema, PaginatedResponse


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
    comprehension_score: float | None = Field(None, ge=0, le=100)  # F-113
    status: Literal["pending", "completed", "cancelled"] = "pending"  # F-113
    scheduled_date: datetime | None = None
    notes: str | None = None
    recommendation: str | None = None

    @model_validator(mode="after")
    def _check_ar_level_order(self):
        # F-113：AR 等级倒挂拒绝（after < before）
        if (
            self.ar_level_before is not None
            and self.ar_level_after is not None
            and self.ar_level_after < self.ar_level_before
        ):
            raise ValueError("ar_level_after 不能小于 ar_level_before")
        return self


class AssessmentUpdateRequest(BaseSchema):
    """更新评估请求"""

    ar_level_before: float | None = None
    ar_level_after: float | None = None
    comprehension_score: float | None = Field(None, ge=0, le=100)  # F-113
    status: Literal["pending", "completed", "cancelled"] | None = None  # F-113
    scheduled_date: datetime | None = None
    completed_date: datetime | None = None
    notes: str | None = None
    recommendation: str | None = None

    @model_validator(mode="after")
    def _check_ar_level_order(self):
        if (
            self.ar_level_before is not None
            and self.ar_level_after is not None
            and self.ar_level_after < self.ar_level_before
        ):
            raise ValueError("ar_level_after 不能小于 ar_level_before")
        return self


class AssessmentListResponse(PaginatedResponse[AssessmentResponse]):
    """评估列表响应"""

    stats: dict = {}
