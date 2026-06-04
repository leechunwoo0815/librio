# backend/services/book_service.py
"""
[What] 图书业务逻辑层
[Why] 封装图书相关的业务规则
[How] 调用仓库层，实现业务逻辑
"""

from backend.repositories.book_repo import BookRepository
from backend.schemas.book import (
    BookCreate, BookResponse, BookSearch,
    BookListResponse
)
from backend.models.book import Book
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BookService:
    """
    [What] 图书服务类
    [Why] 封装图书业务逻辑
    [How] 注入仓库层，实现业务规则
    """

    def __init__(self, book_repo: BookRepository):
        self.book_repo = book_repo

    def search_books(self, search_params: BookSearch) -> BookListResponse:
        """
        搜索图书
        """
        ar_min = None
        ar_max = None

        if search_params.ar_level:
            parts = search_params.ar_level.replace("AR", "").split("-")
            if len(parts) == 2:
                ar_min = float(parts[0])
                ar_max = float(parts[1])

        items, total = self.book_repo.search(
            keyword=search_params.keyword,
            ar_min=ar_min,
            ar_max=ar_max,
            age_min=search_params.age_min,
            age_max=search_params.age_max,
            theme=search_params.theme,
            page=search_params.page,
            page_size=search_params.page_size
        )

        return BookListResponse(
            total=total,
            items=[BookResponse.model_validate(item) for item in items]
        )

    def get_book_detail(self, book_id: int) -> Optional[BookResponse]:
        """获取图书详情"""
        book = self.book_repo.get_by_id(book_id)
        if not book:
            return None
        return BookResponse.model_validate(book)

    def create_book(self, book_data: BookCreate) -> BookResponse:
        """创建图书"""
        existing = self.book_repo.get_by_isbn(book_data.isbn)
        if existing:
            raise ValueError("ISBN已存在")

        book = Book(**book_data.model_dump())
        created = self.book_repo.create(book)
        return BookResponse.model_validate(created)
