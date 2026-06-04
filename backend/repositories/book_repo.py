# backend/repositories/book_repo.py
"""
[What] 图书数据访问层
[Why] 封装数据库操作，与业务逻辑解耦
[How] 使用SQLAlchemy ORM查询
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.models.book import Book
from typing import Optional


class BookRepository:
    """
    [What] 图书仓库类
    [Why] 封装图书相关的数据库操作
    [How] 注入数据库会话，执行CRUD操作
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, book_id: int) -> Optional[Book]:
        """根据ID查询图书"""
        return self.db.query(Book).filter(
            Book.id == book_id,
            Book.is_deleted == 0
        ).first()

    def get_by_isbn(self, isbn: str) -> Optional[Book]:
        """根据ISBN查询图书"""
        return self.db.query(Book).filter(
            Book.isbn == isbn,
            Book.is_deleted == 0
        ).first()

    def search(self, keyword: Optional[str] = None, ar_min: Optional[float] = None,
               ar_max: Optional[float] = None, age_min: Optional[int] = None,
               age_max: Optional[int] = None, theme: Optional[str] = None,
               page: int = 1, page_size: int = 20) -> tuple[list[Book], int]:
        """
        搜索图书
        返回: (图书列表, 总数)
        """
        query = self.db.query(Book).filter(Book.is_deleted == 0)

        if keyword:
            query = query.filter(
                or_(
                    Book.title.like(f"%{keyword}%"),
                    Book.author.like(f"%{keyword}%")
                )
            )

        if ar_min is not None:
            query = query.filter(Book.ar_value >= ar_min)
        if ar_max is not None:
            query = query.filter(Book.ar_value <= ar_max)

        if age_min is not None:
            query = query.filter(Book.age_max >= age_min)
        if age_max is not None:
            query = query.filter(Book.age_min <= age_max)

        if theme:
            query = query.filter(Book.theme == theme)

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    def create(self, book: Book) -> Book:
        """创建图书"""
        self.db.add(book)
        self.db.commit()
        self.db.refresh(book)
        return book

    def update(self, book: Book) -> Book:
        """更新图书"""
        self.db.commit()
        self.db.refresh(book)
        return book
