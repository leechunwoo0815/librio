# backend/domain/activity/schemas.py
"""活动域 Pydantic 模型"""

from datetime import datetime
from decimal import Decimal
from pydantic import Field
from backend.common.base_schema import BaseSchema


class ActivityResponse(BaseSchema):
    id: int
    title: str
    description: str | None = None
    type: int | None = None
    is_free: int | None = 1
    price: Decimal | None = None
    cover: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    enroll_deadline: datetime | None = None
    venue_id: int | None = None
    location: str | None = None
    status: int = 0
    max_participants: int = 0
    current_participants: int = 0
    create_time: datetime


class BatchCheckinRequest(BaseSchema):
    """批量签到请求"""

    child_ids: list[int] = Field(default_factory=list, description="孩子ID列表")


class ActivityEnrollRequest(BaseSchema):
    child_id: int = Field(..., description="孩子ID")
    activity_id: int = Field(..., description="活动ID")
