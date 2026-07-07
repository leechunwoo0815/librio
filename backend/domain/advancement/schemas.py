# backend/domain/advancement/schemas.py
"""晋级域 Pydantic 模型 — 级别/测验/成就"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.base_schema import BaseSchema


# ==================== 级别 ====================


class LevelResponse(BaseSchema):
    id: int
    name: str
    badge_icon: str | None = None
    badge_emoji: str | None = None
    sort_order: int = 0
    required_books: int = 5
    required_quiz_pass_rate: Decimal = Decimal("0.80")
    require_teacher_review: bool = False
    max_borrow_count: int = 1
    max_ar_level: Decimal | None = None


class ChildLevelResponse(BaseSchema):
    id: int
    child_id: int
    level_id: int
    level_name: str | None = None
    achieved_at: datetime | None = None
    books_read_at_level: int = 0
    quizzes_passed_at_level: int = 0
    is_current: bool = True


# ==================== 测验 ====================


class QuizStartRequest(BaseSchema):
    book_id: int
    submission_id: int | None = None


class QuizResponse(BaseSchema):
    id: int
    child_id: int
    book_id: int
    status: int = 0
    total_questions: int = 5
    correct_count: int = 0
    score: Decimal | None = None


class SubmitAnswerRequest(BaseSchema):
    quiz_id: int
    question_id: int
    selected_answer: str = Field(..., min_length=1, max_length=1)


class QuizResultResponse(BaseSchema):
    quiz: QuizResponse
    passed: bool
    word_count: int = 0


class CreateQuestionRequest(BaseSchema):
    """创建题库题目请求"""

    book_id: int
    question_text: str = Field(..., min_length=1)
    option_a: str = Field(..., min_length=1)
    option_b: str = Field(..., min_length=1)
    option_c: str | None = None
    option_d: str | None = None
    correct_answer: str = Field(..., min_length=1, max_length=1)
    difficulty: int = Field(default=1, ge=1, le=5)
    explanation: str | None = None
    created_by: int | None = None


class QuestionResponse(BaseSchema):
    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str | None = None
    option_d: str | None = None
    difficulty: int = 1


# ==================== 成就 ====================


class AchievementResponse(BaseSchema):
    id: int
    name: str
    description: str | None = None
    type: int
    badge_icon: str | None = None
    badge_emoji: str | None = None
    trigger_condition: str | None = None


# ==================== 排行榜 ====================


class LeaderboardEntryResponse(BaseSchema):
    """排行榜条目"""

    rank: int
    child_id: int
    display_name: str
    total_words: int = 0
    total_books: int | None = None
    streak_days: int | None = None
    medal: str | None = None


class ChildAchievementResponse(BaseSchema):
    id: int
    child_id: int
    achievement_id: int
    achieved_at: datetime | None = None
    context_data: str | None = None
    achievement_name: str | None = None
    achievement_emoji: str | None = None
