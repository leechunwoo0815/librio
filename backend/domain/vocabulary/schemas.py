# backend/domain/vocabulary/schemas.py
"""词汇域 Pydantic 模型"""

from datetime import datetime

from pydantic import Field

from backend.common.base_schema import BaseSchema


class WordLookupResponse(BaseSchema):
    """查词响应"""

    id: int
    word: str
    phonetic: str | None = None
    audio_url: str | None = None
    part_of_speech: str | None = None
    chinese_meaning: str | None = None
    example_sentence: str | None = None
    level: str | None = None
    source: str = "ecdict"


class AddVocabRequest(BaseSchema):
    """添加生词请求"""

    word: str = Field(..., description="英文单词")
    child_id: int | None = Field(
        None, description="孩子ID（可选，默认用当前用户的孩子）"
    )
    book_id: int | None = Field(None, description="来源图书ID")


class VocabResponse(BaseSchema):
    """生词本条目响应"""

    id: int
    word: str
    phonetic: str | None = None
    audio_url: str | None = None
    chinese_meaning: str | None = None
    status: int = 0
    lookup_count: int = 1
    last_review_time: datetime | None = None
    create_time: datetime | None = None
    is_new: bool = False


class VocabStatsResponse(BaseSchema):
    """生词统计响应"""

    learning: int
    mastered: int
    total: int
