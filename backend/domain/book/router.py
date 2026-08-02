# backend/domain/book/router.py
"""图书域 API 路由 — 搜索、详情、创建、副本管理"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_book_service
from backend.domain.book.schemas import (
    BookListResponse,
    BookResponse,
    BookSearch,
)
from backend.domain.book.service import BookService
from backend.middleware.rate_limit import rate_limit

router = APIRouter(prefix="/book", tags=["图书"])


@router.get(
    "/search",
    response_model=BookListResponse,
    dependencies=[Depends(rate_limit(30, 60))],
)
def search_books(
    keyword: str | None = None,
    ar_level: str | None = None,
    age_range: str | None = None,
    theme: str | None = None,
    child_id: int | None = Query(None, description="孩子ID（H2：传入时标记'挑战'书）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    book_service: BookService = Depends(get_book_service),
):
    """搜索图书 — 多条件 + 分页"""
    search_params = BookSearch(
        keyword=keyword,
        ar_level=ar_level,
        age_range=age_range,
        theme=theme,
        page=page,
        page_size=page_size,
    )
    return book_service.search_books(search_params, child_id=child_id)


@router.get("/{book_id}", response_model=BookResponse)
def get_book_detail(
    book_id: int,
    book_service: BookService = Depends(get_book_service),
):
    """获取图书详情"""
    return book_service.get_book_detail(book_id)


@router.get("/{book_id}/related", response_model=list[BookResponse])
def get_related_books(
    book_id: int,
    limit: int = Query(6, ge=1, le=20),
    book_service: BookService = Depends(get_book_service),
):
    """获取相关图书推荐（同主题）"""
    return book_service.get_related_books(book_id, limit)
