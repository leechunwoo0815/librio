# backend/domain/parent_course_time/schemas.py
"""亲子课时间段 Pydantic 模型"""

from datetime import datetime

from pydantic import Field

from backend.common.base_schema import BaseSchema


class ParentCourseTimeCreate(BaseSchema):
    """创建时间段请求"""

    venue_id: int = Field(..., description="场馆ID")
    course_date: str = Field(..., description="日期 YYYY-MM-DD")
    start_time: str = Field(..., description="开始时间 HH:MM")
    end_time: str = Field(..., description="结束时间 HH:MM")
    max_participants: int = Field(default=10, description="最大名额")


class ParentCourseTimeUpdate(BaseSchema):
    """更新时间段请求"""

    course_date: str | None = Field(None, description="日期 YYYY-MM-DD")
    start_time: str | None = Field(None, description="开始时间 HH:MM")
    end_time: str | None = Field(None, description="结束时间 HH:MM")
    max_participants: int | None = Field(None, description="最大名额")
    status: int | None = Field(None, description="状态: 1=可约 0=已满 -1=关闭")


class ParentCourseTimeResponse(BaseSchema):
    """时间段响应"""

    id: int
    venue_id: int
    course_date: str
    start_time: str
    end_time: str
    max_participants: int
    current_participants: int
    status: int
    create_time: datetime | None = None
