# backend/domain/book/schemas.py
"""图书域 Pydantic 模型 — 请求/响应数据验证"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.base_schema import BaseSchema, PaginatedResponse


class BookCreate(BaseSchema):
    """创建图书请求"""

    isbn: str = Field(..., min_length=10, max_length=20, description="ISBN号")
    title: str = Field(..., max_length=255, description="书名")
    author: str = Field(..., max_length=100, description="作者")
    publisher: str | None = Field(None, max_length=100, description="出版社")
    ar_value: Decimal = Field(..., description="AR阅读等级")
    lexile_value: int | None = Field(None, description="蓝思值")
    age_min: int = Field(..., ge=3, le=15, description="适合最小年龄")
    age_max: int = Field(..., ge=3, le=15, description="适合最大年龄")
    theme: str | None = Field(None, max_length=50, description="主题")
    summary: str | None = Field(None, description="内容简介")
    cover: str | None = Field(None, max_length=255, description="封面URL")
    total_pages: int | None = Field(None, description="总页数")
    # V2.0 扩展字段
    word_count: int | None = Field(None, description="总词数")
    has_audio: int = Field(0, description="是否配有音频")
    audio_url: str | None = Field(None, description="整书音频URL")
    # V3.1 OMO 字段
    total_stock: int = Field(0, description="实体书库存总数")
    offline_available: int = Field(0, description="是否支持线下借阅")


class BookResponse(BaseSchema):
    """图书响应"""

    id: int
    isbn: str
    title: str
    author: str
    publisher: str | None = None
    ar_value: Decimal
    lexile_value: int | None = None
    age_min: int
    age_max: int
    theme: str | None = None
    summary: str | None = None
    cover: str | None = None
    total_pages: int | None = None
    word_count: int | None = None
    has_audio: int = 0
    audio_url: str | None = None
    difficulty_level: str | None = None
    total_stock: int = 0
    available_stock: int = 0
    offline_available: int = 0
    question_count: int | None = None
    create_time: datetime


class BookSearch(BaseSchema):
    """图书搜索请求"""

    keyword: str | None = Field(None, description="搜索关键词")
    ar_level: str | None = Field(None, description="AR级别范围")
    age_range: str | None = Field(None, description="年龄段")
    theme: str | None = Field(None, description="主题")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页条数")


class BookCopyResponse(BaseSchema):
    """实体书副本响应"""

    id: int
    book_id: int
    barcode: str
    status: int
    condition_note: str | None = None
    location: str | None = None
    create_time: datetime


class BookCopyCreate(BaseSchema):
    """创建实体书副本请求"""

    book_id: int = Field(..., description="关联图书ID")
    barcode: str = Field(..., max_length=50, description="副本条码")
    condition_note: str | None = Field(None, description="状况备注")
    location: str | None = Field(None, max_length=50, description="存放位置")


# 分页响应别名
BookListResponse = PaginatedResponse[BookResponse]
