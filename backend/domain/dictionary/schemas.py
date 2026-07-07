# backend/domain/dictionary/schemas.py
"""词库域 Pydantic 模型"""

from datetime import datetime
from pydantic import Field, ConfigDict
from backend.common.base_schema import BaseSchema


class WordResponse(BaseSchema):
    """词条响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    word: str
    phonetic: str | None = None
    pos: str | None = None  # 映射自 part_of_speech
    cn_definition: str | None = None  # 映射自 chinese_meaning
    example_sentence: str | None = None
    ar_level: str | None = None  # 映射自 level
    create_time: datetime | None = None


class WordCreateRequest(BaseSchema):
    """创建词条请求"""
    word: str = Field(..., min_length=1, max_length=100)
    phonetic: str | None = None
    pos: str | None = None  # 映射到 part_of_speech
    cn_definition: str | None = None  # 映射到 chinese_meaning
    example_sentence: str | None = None
    ar_level: str | None = None  # 映射到 level


class WordUpdateRequest(BaseSchema):
    """更新词条请求"""
    word: str | None = Field(None, min_length=1, max_length=100)
    phonetic: str | None = None
    pos: str | None = None
    cn_definition: str | None = None
    example_sentence: str | None = None
    ar_level: str | None = None


class WordListResponse(BaseSchema):
    """词条列表响应"""
    items: list[WordResponse]
    total: int
    page: int
    page_size: int
