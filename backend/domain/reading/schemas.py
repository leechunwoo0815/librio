# backend/domain/reading/schemas.py
"""阅读域 Pydantic 模型"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from backend.common.base_schema import BaseSchema


class BookPageResponse(BaseSchema):
    """图书页面响应"""

    id: int
    book_id: int
    page_number: int
    content_type: int = 0
    text_content: str | None = None
    image_url: str | None = None
    audio_url: str | None = None
    audio_duration: int | None = None


class ProgressResponse(BaseSchema):
    """阅读进度响应"""

    id: int
    child_id: int
    book_id: int
    current_page: int
    total_pages: int
    progress_pct: Decimal = 0
    last_read_time: datetime | None = None
    is_finished: int = 0
    finish_time: datetime | None = None


class SaveProgressRequest(BaseSchema):
    """保存进度请求"""

    book_id: int
    current_page: int
    total_pages: int


class StartSessionRequest(BaseSchema):
    """开始阅读会话请求"""

    book_id: int
    child_id: int | None = None


class EndSessionRequest(BaseSchema):
    """结束阅读会话请求"""

    pages_read: int = 0
    words_read: int = 0
    reading_minutes: int = 0


class SessionResponse(BaseSchema):
    """阅读会话响应"""

    id: int
    child_id: int
    book_id: int
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: int = 0
    pages_read: int = 0
    words_read: int = 0


class CheckInResponse(BaseSchema):
    """打卡响应"""

    id: int
    child_id: int
    check_date: date
    check_type: int
    reading_minutes: int = 0
    words_read: int = 0


class StreakResponse(BaseSchema):
    """连续打卡响应"""

    current_streak: int
    longest_streak: int


# ==================== 语音朗读 ====================


class SaveRecordingRequest(BaseSchema):
    """保存录音请求"""

    child_id: int
    book_id: int
    text: str = Field(..., min_length=1)
    audio_url: str = Field(..., min_length=1)
    duration: int = Field(..., gt=0)
    page_id: int | None = None


class VoiceRecordingResponse(BaseSchema):
    """语音录音响应"""

    id: int
    audio_url: str
    duration_seconds: int


class VoiceRecordingDetailResponse(BaseSchema):
    """语音录音详情"""

    id: int
    book_id: int
    text_content: str
    audio_url: str
    duration_seconds: int
    pronunciation_score: float | None = None
    create_time: datetime | None = None


class CheckinRecordResponse(BaseSchema):
    """打卡记录响应（前端最近打卡列表）"""

    date: str
    book_name: str
    pages: str
