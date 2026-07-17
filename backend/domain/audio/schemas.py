# backend/domain/audio/schemas.py
"""音频域 Pydantic 模型"""

from datetime import datetime
from pydantic import Field
from backend.common.base_schema import BaseSchema, PaginatedResponse


class AudioResponse(BaseSchema):
    """音频响应"""
    id: int
    filename: str
    file_url: str
    book_id: int | None = None
    book_title: str | None = None
    page_number: int | None = None
    page_label: str | None = None
    duration: str | None = None
    duration_seconds: int | None = None
    reader: str | None = None
    status: str = "linked"
    file_size: int | None = None
    create_time: datetime | None = None


class AudioCreateRequest(BaseSchema):
    """创建音频请求"""
    filename: str = Field(..., min_length=1, max_length=255)
    file_url: str = Field(..., min_length=1, max_length=500)
    book_id: int | None = None
    page_number: int | None = None
    reader: str | None = None
    duration: str | None = None
    duration_seconds: int | None = None
    file_size: int | None = None


class AudioUpdateRequest(BaseSchema):
    """更新音频请求"""
    filename: str | None = None
    book_id: int | None = None
    page_number: int | None = None
    reader: str | None = None
    status: str | None = None


class AudioListResponse(PaginatedResponse[AudioResponse]):
    """音频列表响应"""
    stats: dict = {}
