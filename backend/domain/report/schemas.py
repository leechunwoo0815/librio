# backend/domain/report/schemas.py
"""报告域 Pydantic 模型"""

from datetime import datetime


from backend.common.base_schema import BaseSchema


class ObservationReportResponse(BaseSchema):
    id: int
    child_id: int
    teacher_id: int | None = None
    content: str | None = None
    teacher_comment: str | None = None
    total_books_read: int = 0
    total_words_read: int = 0
    total_reading_minutes: int = 0
    quizzes_attempted: int = 0
    quizzes_passed: int = 0
    current_level: str | None = None
    status: int = 0
    period_start: datetime | None = None
    period_end: datetime | None = None
    observation_start: datetime | None = None
    observation_end: datetime | None = None
    generated_at: datetime | None = None
    create_time: datetime | None = None


class LearningReportResponse(BaseSchema):
    id: int
    child_id: int
    ar_level: float | None = None
    total_books: int = 0
    total_words: int = 0
    total_minutes: int = 0
    period_start: datetime | None = None
    period_end: datetime | None = None
    create_time: datetime


# ==================== 观察期报告（旧 migration 扩展） ====================


class ObservationReportDetailResponse(BaseSchema):
    """观察期报告详情"""

    id: int
    child_id: int
    total_books_read: int = 0
    total_words_read: int = 0
    total_reading_minutes: int = 0
    quizzes_attempted: int = 0
    quizzes_passed: int = 0
    current_level: str | None = None
    teacher_comment: str | None = None
    teacher_id: int | None = None
    status: int = 0
    observation_start: datetime | None = None
    observation_end: datetime | None = None
    generated_at: datetime | None = None


class GenerateReportResult(BaseSchema):
    """报告生成结果"""

    child_id: int
    report_id: int


class GenerateReportsResponse(BaseSchema):
    """批量生成报告响应"""

    generated: int
    reports: list[GenerateReportResult]


class MarkViewedResponse(BaseSchema):
    """标记已查看响应"""

    success: bool


class AddCommentResponse(BaseSchema):
    """添加评语响应"""

    success: bool


# ==================== 阅读统计 ====================


class SummaryResponse(BaseSchema):
    """累计统计"""

    total_reading_minutes: int = 0
    total_words_read: int = 0
    books_finished: int = 0
    vocabulary_count: int = 0
    voice_practices: int = 0
    current_streak: int = 0
    longest_streak: int = 0


class TodayStatsResponse(BaseSchema):
    """今日统计"""

    reading_minutes: int = 0
    words_read: int = 0
    pages_read: int = 0


class TrendEntryResponse(BaseSchema):
    """趋势条目"""

    date: str
    reading_minutes: int = 0
    words_read: int = 0


class MonthlyReportResponse(BaseSchema):
    """月报"""

    report_type: str = "monthly"
    period: str = ""
    total_minutes: int = 0
    total_words: int = 0
    books_finished: int = 0
    checkin_days: int = 0
    checkin_rate: int = 0
    current_ar_level: float | None = None
    streak_days: int = 0


class WeeklyReportResponse(BaseSchema):
    """周报"""

    report_type: str = "weekly"
    period: str = ""
    total_minutes: int = 0
    total_words: int = 0
    books_finished: int = 0
    new_vocabulary: int = 0
    voice_practices: int = 0
    checkin_days: int = 0
    current_ar_level: float | None = None
    streak_days: int = 0
    suggestion: str = ""
