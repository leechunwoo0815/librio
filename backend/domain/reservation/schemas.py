# backend/domain/reservation/schemas.py
"""预约域 Pydantic 模型"""

from datetime import datetime

from pydantic import Field

from backend.common.base_schema import BaseSchema


class ReservationCreateRequest(BaseSchema):
    child_id: int = Field(..., description="孩子ID")
    book_id: int = Field(..., description="图书ID")
    venue_id: int | None = Field(None, description="取书场馆")


class ReservationFulfillRequest(BaseSchema):
    reservation_id: int | None = Field(None, description="预约ID（手动取书路径）")
    barcode: str | None = Field(
        None,
        description="取书副本条码（扫码枪；单独提供时自动匹配该书最早待取预约）",
    )


class ReservationResponse(BaseSchema):
    id: int
    child_id: int
    book_id: int
    venue_id: int | None = None
    status: int
    expire_time: datetime
    fulfilled_time: datetime | None = None
    borrow_record_id: int | None = None
    create_time: datetime
    book_title: str | None = None
    book_cover: str | None = None
