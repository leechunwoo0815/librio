# backend/domain/book/service.py
"""图书域业务逻辑 — 搜索、创建、库存管理"""

import logging

from sqlalchemy.orm import Session

from backend.common.exceptions import ConflictError, ValidationError
from backend.domain.book.models import Book, BookCopy
from backend.domain.book.repository import BookRepository, BookCopyRepository
from backend.domain.book.schemas import (
    BookCreate,
    BookListResponse,
    BookResponse,
    BookSearch,
)

logger = logging.getLogger(__name__)


class BookService:
    """图书服务

    架构意图：
      - 搜索走 BookRepository.search()，创建走 BaseRepository.create()
      - V3.1 库存变更通过事件驱动（BookBorrowedEvent → 扣库存）
      - BookCopy 管理在此服务中（同一域内聚合）
    """

    def __init__(self, db: Session):
        self.db = db
        self.book_repo = BookRepository(db)
        self.copy_repo = BookCopyRepository(db)

    def search_books(self, search_params: BookSearch) -> BookListResponse:
        """搜索图书 — 多条件 + 分页"""
        books, total = self.book_repo.search(
            keyword=search_params.keyword,
            ar_level=search_params.ar_level,
            age_range=search_params.age_range,
            theme=search_params.theme,
            page=search_params.page,
            page_size=search_params.page_size,
        )

        # 批量查询每本书的题目数量，避免 N+1
        book_ids = [b.id for b in books]
        question_counts = {}
        if book_ids:
            from sqlalchemy import func
            from backend.domain.advancement.models import QuestionBank

            rows = (
                self.db.query(
                    QuestionBank.book_id,
                    func.count(QuestionBank.id).label("count"),
                )
                .filter(
                    QuestionBank.book_id.in_(book_ids),
                    QuestionBank.is_deleted == 0,
                )
                .group_by(QuestionBank.book_id)
                .all()
            )
            question_counts = {row.book_id: row.count for row in rows}

        items = []
        for b in books:
            resp = BookResponse.model_validate(b)
            resp.question_count = question_counts.get(b.id, 0)
            items.append(resp)

        return BookListResponse.create(
            items=items,
            total=total,
            page=search_params.page,
            page_size=search_params.page_size,
        )

    def get_book_detail(self, book_id: int) -> BookResponse:
        """获取图书详情"""
        book = self.book_repo.get_by_id_or_raise(book_id)
        return BookResponse.model_validate(book)

    def create_book(self, book_data: BookCreate) -> BookResponse:
        """创建图书 — 校验 ISBN 唯一性"""
        existing = self.book_repo.get_by_isbn(book_data.isbn)
        if existing:
            raise ConflictError("ISBN已存在")

        book = Book(
            isbn=book_data.isbn,
            title=book_data.title,
            author=book_data.author,
            publisher=book_data.publisher,
            ar_value=book_data.ar_value,
            lexile_value=book_data.lexile_value,
            age_min=book_data.age_min,
            age_max=book_data.age_max,
            theme=book_data.theme,
            summary=book_data.summary,
            cover=book_data.cover,
            total_pages=book_data.total_pages,
            word_count=book_data.word_count,
            has_audio=book_data.has_audio,
            audio_url=book_data.audio_url,
            total_stock=book_data.total_stock,
            available_stock=book_data.total_stock,  # 初始可借 = 总库存
            offline_available=book_data.offline_available,
        )

        created = self.book_repo.create(book)
        self.db.commit()
        logger.info(f"Book created: id={created.id}, isbn={created.isbn}")
        return BookResponse.model_validate(created)

    def update_book(self, book_id: int, data) -> dict:
        """更新图书"""
        from backend.common.exceptions import NotFoundError
        book = self.book_repo.get_by_id(book_id)
        if not book or book.is_deleted == 1:
            raise NotFoundError("图书不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(book, key):
                setattr(book, key, value)
        self.book_repo.update(book)
        self.db.commit()
        return {"success": True, "message": "图书更新成功"}

    def delete_book(self, book_id: int) -> dict:
        """软删除图书"""
        from backend.common.exceptions import NotFoundError
        book = self.book_repo.get_by_id(book_id)
        if not book or book.is_deleted == 1:
            raise NotFoundError("图书不存在")
        self.book_repo.soft_delete(book_id)
        self.db.commit()
        return {"success": True, "message": "图书已删除"}

    def decrease_available_stock(self, book_id: int) -> None:
        """扣减可借库存 — SQL 原子操作（事件处理器调用，不自行 commit）"""
        updated = (
            self.db.query(Book)
            .filter(
                Book.id == book_id,
                Book.available_stock > 0,
                Book.is_deleted == 0,
            )
            .update({Book.available_stock: Book.available_stock - 1})
        )
        if not updated:
            raise ValidationError("库存不足，无法借出")

    def increase_available_stock(self, book_id: int) -> None:
        """恢复可借库存（事件处理器调用，不自行 commit）"""
        book = self.book_repo.get_by_id(book_id)
        if not book:
            return
        book.available_stock = (book.available_stock or 0) + 1
        self.book_repo.update(book)

    def update_copy_status(self, copy_id: int, status: int) -> None:
        """更新副本状态（事件处理器调用，不自行 commit）"""
        copy = self.copy_repo.get_by_id(copy_id)
        if copy:
            copy.status = status
            self.copy_repo.update(copy)

    def toggle_publish(self, book_id: int) -> dict:
        """切换图书发布状态"""
        from backend.common.exceptions import NotFoundError
        book = self.book_repo.get_by_id(book_id)
        if not book or book.is_deleted == 1:
            raise NotFoundError("图书不存在")
        # SQL 原子更新，避免并发问题
        from sqlalchemy import update
        from backend.domain.book.models import Book
        new_status = 0 if book.is_published == 1 else 1
        self.db.execute(
            update(Book).where(Book.id == book_id).values(is_published=new_status)
        )
        self.db.commit()
        return {"success": True, "is_published": new_status, "message": "发布状态已切换"}

    def create_book_copy_admin(self, book_id: int) -> dict:
        """管理端创建图书副本"""
        import uuid
        from backend.common.exceptions import NotFoundError
        book = self.book_repo.get_by_id(book_id)
        if not book or book.is_deleted == 1:
            raise NotFoundError("图书不存在")
        copy = BookCopy(
            book_id=book_id,
            barcode=f"MW-{uuid.uuid4().hex[:8].upper()}",
            status=1,  # 在架
        )
        created = self.copy_repo.create(copy)
        self.db.commit()
        return {"id": created.id, "barcode": created.barcode, "status": created.status}
