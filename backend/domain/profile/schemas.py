# backend/domain/profile/schemas.py
"""名片域 Pydantic 模型"""

from backend.common.base_schema import BaseSchema


class ProfileResponse(BaseSchema):
    """阅读名片响应"""

    child_id: int
    name: str | None = None
    english_name: str | None = None
    age: int | None = None
    grade: str | None = None
    total_books_finished: int = 0
    total_words_read: int = 0
    total_reading_minutes: int = 0
    current_streak_days: int = 0
    longest_streak_days: int = 0
    current_level: dict | None = None
    achievement_count: int = 0
    achievements: list = []
