# backend/routers/book.py
"""
[What] 图书API路由
[Why] 定义图书相关的API端点
[How] 使用FastAPI路由器
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.repositories.book_repo import BookRepository
from backend.services.book_service import BookService
from backend.schemas.book import (
    BookCreate, BookResponse, BookSearch,
    BookListResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/book", tags=["图书"])


def get_book_service(db: Session = Depends(get_db)) -> BookService:
    """获取图书服务实例（依赖注入）"""
    book_repo = BookRepository(db)
    return BookService(book_repo)


@router.get("/search", response_model=BookListResponse)
async def search_books(
    keyword: str = Query(None, description="关键词"),
    ar_level: str = Query(None, description="AR等级范围，如 AR1-AR3"),
    age_min: int = Query(None, description="最小年龄"),
    age_max: int = Query(None, description="最大年龄"),
    theme: str = Query(None, description="主题"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    book_service: BookService = Depends(get_book_service)
):
    """搜索图书"""
    search_params = BookSearch(
        keyword=keyword,
        ar_level=ar_level,
        age_min=age_min,
        age_max=age_max,
        theme=theme,
        page=page,
        page_size=page_size
    )
    return book_service.search_books(search_params)


@router.get("/{book_id}", response_model=BookResponse)
async def get_book_detail(
    book_id: int,
    book_service: BookService = Depends(get_book_service)
):
    """获取图书详情"""
    book = book_service.get_book_detail(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="图书不存在")
    return book


@router.post("/", response_model=BookResponse)
async def create_book(
    book_data: BookCreate,
    book_service: BookService = Depends(get_book_service)
):
    """创建图书"""
    try:
        return book_service.create_book(book_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
