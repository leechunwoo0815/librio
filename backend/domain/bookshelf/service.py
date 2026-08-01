# backend/domain/bookshelf/service.py
"""书架域业务逻辑 — V3.1: 想读清单（无限量，与借阅无关；D5: favorites 已并入）"""

import logging

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.exceptions import ConflictError, NotFoundError
from backend.common.types import BookshelfStatus
from backend.domain.book.models import Book
from backend.domain.bookshelf.models import Bookshelf
from backend.domain.bookshelf.repository import BookshelfRepository
from backend.domain.bookshelf.schemas import (
    BookshelfResponse,
)

logger = logging.getLogger(__name__)


class BookshelfService:
    """书架服务

    V3.1 语义变更：
      - 书架 = 想读清单 + 已读记录（无上限）
      - 借阅功能由 borrow 域处理，与书架无关
      - 测验通过后不再自动还书（因为书架不是借阅）
    """

    def __init__(self, db: Session):
        self.db = db
        self.shelf_repo = BookshelfRepository(db)
        self.book_repo = BaseRepository(db, Book)

    def add_to_shelf(self, child_id: int, book_id: int) -> BookshelfResponse:
        """加入想读清单"""
        from backend.common.config_service import ConfigService

        # 检查图书存在
        self.book_repo.get_by_id_or_raise(book_id)

        # 检查是否已在书架
        existing = self.shelf_repo.get_active_entry(child_id, book_id)
        if existing:
            raise ConflictError("该书已在书架中")

        # 书架容量限制（C4：默认 100 本）
        limit = ConfigService.get_int(self.db, "bookshelf_limit", 100)
        if limit > 0:
            current_count = self.shelf_repo.count_active(child_id)
            if current_count >= limit:
                raise ConflictError(f"书架已满（上限 {limit} 本），请先移除后再添加")

        entry = Bookshelf(
            child_id=child_id,
            book_id=book_id,
            status=BookshelfStatus.WANT_READ,
        )
        created = self.shelf_repo.create(entry)
        self.db.commit()
        logger.info(f"Book added to shelf: child={child_id}, book={book_id}")
        self.db.refresh(created)
        book = created.book
        return BookshelfResponse(
            id=created.id,
            child_id=created.child_id,
            book_id=created.book_id,
            status=created.status,
            book_title=book.title if book else None,
            book_cover=book.cover if book else None,
            add_time=created.create_time,
            title=book.title if book else None,
            author=book.author if book else None,
            ar_value=float(book.ar_value) if book and book.ar_value else None,
            word_count=book.word_count if book else None,
        )

    def mark_as_finished(self, child_id: int, book_id: int) -> BookshelfResponse:
        """标记为已读"""
        entry = self.shelf_repo.get_active_entry(child_id, book_id)
        if not entry:
            raise NotFoundError("该书不在书架中")

        entry.status = BookshelfStatus.FINISHED
        self.shelf_repo.update(entry)
        self.db.commit()
        self.db.refresh(entry)
        book = entry.book
        return BookshelfResponse(
            id=entry.id,
            child_id=entry.child_id,
            book_id=entry.book_id,
            status=entry.status,
            book_title=book.title if book else None,
            book_cover=book.cover if book else None,
            add_time=entry.create_time,
            title=book.title if book else None,
            author=book.author if book else None,
            ar_value=float(book.ar_value) if book and book.ar_value else None,
        )

    def remove_from_shelf(self, child_id: int, book_id: int) -> dict:
        """从书架移除"""
        entry = self.shelf_repo.get_active_entry(child_id, book_id)
        if not entry:
            raise NotFoundError("该书不在书架中")
        entry.status = BookshelfStatus.REMOVED
        self.shelf_repo.update(entry)
        self.db.commit()
        return {"id": entry.id, "status": "removed"}

    def get_shelf(self, child_id: int) -> list[BookshelfResponse]:
        """获取书架列表（C4：附库存状态供前端标灰）"""
        entries = self.shelf_repo.get_shelf(child_id)
        results = []
        for e in entries:
            book = e.book
            stock = (book.available_stock or 0) if book else 0
            resp = BookshelfResponse(
                id=e.id,
                child_id=e.child_id,
                book_id=e.book_id,
                status=e.status,
                book_title=book.title if book else None,
                book_cover=book.cover if book else None,
                add_time=e.create_time,
                title=book.title if book else None,
                author=book.author if book else None,
                ar_value=float(book.ar_value) if book and book.ar_value else None,
                word_count=book.word_count if book else None,
                available_stock=stock,
                in_stock=stock > 0,
            )
            results.append(resp)
        return results
