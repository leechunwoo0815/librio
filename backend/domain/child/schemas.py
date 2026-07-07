# backend/domain/child/schemas.py
"""孩子域 Pydantic 模型 — 请求/响应数据验证"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.base_schema import BaseSchema


class ChildCreate(BaseSchema):
    """创建孩子请求"""

    name: str = Field(..., max_length=50, description="孩子中文姓名")
    english_name: str | None = Field(None, max_length=50, description="孩子英文姓名")
    age: int = Field(..., ge=3, le=15, description="孩子年龄(3-15)")
    grade: str = Field(..., max_length=20, description="年级")
    venue_id: int | None = Field(None, description="所属场馆ID")


class ChildResponse(BaseSchema):
    """孩子响应"""

    id: int
    user_id: int
    name: str
    english_name: str | None = None
    age: int
    grade: str
    status: int
    member_start_time: datetime | None = None
    member_expire_time: datetime | None = None
    ar_level: float | None = None
    teacher_id: int | None = None
    venue_id: int | None = None

    # 阅读统计
    total_reading_minutes: int = 0
    total_words_read: int = 0
    total_books_finished: int = 0
    current_streak_days: int = 0
    longest_streak_days: int = 0

    # V3.1
    deposit_status: int | None = 0
    outstanding_fines: Decimal | None = Decimal("0")

    create_time: datetime


class ChildStatusUpdate(BaseSchema):
    """更新孩子会员状态请求"""

    status: int = Field(..., description="新状态")
    member_start_time: datetime | None = Field(None, description="会员开始时间")
    member_expire_time: datetime | None = Field(None, description="会员到期时间")


class ChildUpdate(BaseSchema):
    """更新孩子基本信息"""

    name: str | None = Field(None, max_length=50, description="孩子中文姓名")
    english_name: str | None = Field(None, max_length=50, description="孩子英文姓名")
    age: int | None = Field(None, ge=3, le=15, description="孩子年龄")
    grade: str | None = Field(None, max_length=20, description="年级")


class TransferBenefitRequest(BaseSchema):
    """权益转让请求"""

    source_child_id: int = Field(..., description="转出孩子ID")
    target_child_id: int = Field(..., description="接收孩子ID")


class BorrowPermissionResponse(BaseSchema):
    """借书权限检查响应"""

    child_id: int
    can_borrow: bool
