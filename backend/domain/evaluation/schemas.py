# backend/domain/evaluation/schemas.py
"""测评域 Pydantic 模型 — AR测评、观察期评价"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.base_schema import BaseSchema


# ============================================================
# AR测评
# ============================================================


class AREvaluationCreate(BaseSchema):
    """创建AR测评请求"""

    child_id: int = Field(..., description="孩子ID")
    ar_level: Decimal = Field(..., description="AR级别")
    evaluation_date: datetime = Field(..., description="测评日期")
    teacher_id: int | None = Field(None, description="老师ID")
    remark: str | None = Field(None, description="备注")


class AREvaluationResponse(BaseSchema):
    """AR测评响应"""

    id: int
    child_id: int
    ar_level: Decimal
    evaluation_date: datetime
    teacher_id: int | None = None
    remark: str | None = None
    create_time: datetime | None = None
