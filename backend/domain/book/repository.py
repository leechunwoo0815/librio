# backend/domain/book/repository.py
"""图书域数据访问层 — 继承 BaseRepository，扩展搜索和 ISBN 查询"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.book.models import Book, BookCopy


class BookRepository(BaseRepository[Book]):
    """图书仓库 — 扩展搜索、ISBN 查询"""

    def __init__(self, db: Session):
        super().__init__(db, Book)

    def get_by_isbn(self, isbn: str) -> Book | None:
        """根据 ISBN 查询图书"""
        return self.get_by_field("isbn", isbn)

    def search(
        self,
        keyword: str | None = None,
        ar_level: str | None = None,
        age_range: str | None = None,
        theme: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Book], int]:
        """多条件搜索图书，返回 (结果列表, 总数)"""
        query = self.db.query(Book).filter(Book.is_deleted == 0)

        # 关键词搜索（标题/作者/ISBN）
        if keyword:
            query = query.filter(
                or_(
                    Book.title.like(f"%{keyword}%"),
                    Book.author.like(f"%{keyword}%"),
                    Book.isbn.like(f"%{keyword}%"),
                )
            )

        # AR 级别筛选
        if ar_level:
            try:
                parts = ar_level.replace("AR", "").split("-")
                if len(parts) == 2:
                    ar_min, ar_max = float(parts[0]), float(parts[1])
                    query = query.filter(
                        Book.ar_value >= ar_min, Book.ar_value <= ar_max
                    )
            except (ValueError, IndexError):
                pass

        # 年龄段筛选
        if age_range:
            try:
                parts = age_range.replace("岁", "").split("-")
                if len(parts) == 2:
                    a_min, a_max = int(parts[0]), int(parts[1])
                    query = query.filter(Book.age_min >= a_min, Book.age_max <= a_max)
            except (ValueError, IndexError):
                pass

        # 主题筛选
        if theme:
            query = query.filter(Book.theme == theme)

        total = query.count()
        offset = (page - 1) * page_size
        books = query.offset(offset).limit(page_size).all()
        return books, total


class BookCopyRepository(BaseRepository[BookCopy]):
    """实体书副本仓库"""

    def __init__(self, db: Session):
        super().__init__(db, BookCopy)

    def get_by_barcode(self, barcode: str) -> BookCopy | None:
        """根据条码查询副本"""
        return self.get_by_field("barcode", barcode)

    def get_available_copies(self, book_id: int) -> list[BookCopy]:
        """获取某本书的可借副本"""
        from backend.common.types import BookCopyStatus

        return self.list_all(
            limit=100, book_id=book_id, status=BookCopyStatus.AVAILABLE
        )
