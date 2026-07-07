# backend/domain/bookshelf/schemas.py
"""书架域 Pydantic 模型 — V3.1 语义变更：想读清单 + 收藏夹"""

from datetime import datetime

from pydantic import Field

from backend.common.base_schema import BaseSchema


class BookshelfAddRequest(BaseSchema):
    """加入想读清单请求"""

    book_id: int = Field(..., description="图书ID")


class BookshelfResponse(BaseSchema):
    """书架条目响应"""

    id: int
    child_id: int
    book_id: int
    status: int = Field(description="1=想读 2=已读 3=移除")
    book_title: str | None = None
    book_cover: str | None = None
    add_time: datetime | None = None
    finish_time: datetime | None = None


class FavoriteAddRequest(BaseSchema):
    """收藏请求"""

    book_id: int = Field(..., description="图书ID")


class FavoriteResponse(BaseSchema):
    """收藏响应"""

    id: int
    child_id: int
    book_id: int
    book_title: str | None = None
    book_cover: str | None = None
    create_time: datetime | None = None
