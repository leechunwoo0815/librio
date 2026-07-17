# backend/domain/book/router.py
"""图书域 API 路由 — 搜索、详情、创建、副本管理"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_book_service
from backend.domain.book.schemas import (
    BookCreate,
    BookListResponse,
    BookResponse,
    BookSearch,
    BookCopyCreate,
    BookCopyResponse,
)
from backend.domain.book.service import BookService
from backend.middleware.admin_rbac import require_perm
from backend.middleware.rate_limit import rate_limit

router = APIRouter(prefix="/book", tags=["图书"])


@router.get("/search", response_model=BookListResponse, dependencies=[Depends(rate_limit(30, 60))])
def search_books(
    keyword: str | None = None,
    ar_level: str | None = None,
    age_range: str | None = None,
    theme: str | None = None,
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
    return book_service.search_books(search_params)


@router.get("/{book_id}", response_model=BookResponse)
def get_book_detail(
    book_id: int,
    book_service: BookService = Depends(get_book_service),
):
    """获取图书详情"""
    return book_service.get_book_detail(book_id)


@router.post("/", response_model=BookResponse, status_code=201)
def create_book(
    book_data: BookCreate,
    book_service: BookService = Depends(get_book_service),
    admin=Depends(require_perm("book.create")),
):
    """创建图书（管理员操作）"""
    return book_service.create_book(book_data)


@router.post("/{book_id}/copies", response_model=BookCopyResponse, status_code=201)
def create_book_copy(
    book_id: int,
    copy_data: BookCopyCreate,
    book_service: BookService = Depends(get_book_service),
    admin=Depends(require_perm("bookcopy.create")),
):
    """创建实体书副本（V3.1，管理员操作）"""
    copy_data.book_id = book_id
    return book_service.create_book_copy(copy_data)
