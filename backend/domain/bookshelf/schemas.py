# backend/domain/bookshelf/schemas.py
"""书架域 Pydantic 模型 — V3.1 语义变更：想读清单（D5: favorites 已并入）"""

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
    finish_date: str | None = None
    title: str | None = None
    author: str | None = None
    ar_value: float | None = None
    word_count: int | None = None
    cover_emoji: str | None = None
    cover_bg: str | None = None
    available_stock: int | None = Field(
        None, description="当前可借库存（C4：无库存标灰）"
    )
    in_stock: bool | None = Field(
        None, description="是否有库存（C4：False 时前端标灰'暂不可借'）"
    )
