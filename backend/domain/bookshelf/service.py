# backend/domain/bookshelf/service.py
"""书架域业务逻辑 — V3.1: 想读清单 + 收藏夹（无限量，与借阅无关）"""

import logging

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.exceptions import ConflictError, NotFoundError
from backend.common.types import BookshelfStatus
from backend.domain.book.models import Book
from backend.domain.bookshelf.models import Bookshelf, Favorites
from backend.domain.bookshelf.repository import BookshelfRepository, FavoritesRepository
from backend.domain.bookshelf.schemas import (
    BookshelfResponse,
    FavoriteResponse,
)

logger = logging.getLogger(__name__)


class BookshelfService:
    """书架服务

    V3.1 语义变更：
      - 书架 = 想读清单 + 已读记录 + 收藏夹（无上限）
      - 借阅功能由 borrow 域处理，与书架无关
      - 测验通过后不再自动还书（因为书架不是借阅）
    """

    def __init__(self, db: Session):
        self.db = db
        self.shelf_repo = BookshelfRepository(db)
        self.fav_repo = FavoritesRepository(db)
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

        # 书架容量限制
        limit = ConfigService.get_int(self.db, "bookshelf_limit", 0)
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
        return BookshelfResponse.model_validate(created)

    def mark_as_finished(self, child_id: int, book_id: int) -> BookshelfResponse:
        """标记为已读"""
        entry = self.shelf_repo.get_active_entry(child_id, book_id)
        if not entry:
            raise NotFoundError("该书不在书架中")

        entry.status = BookshelfStatus.FINISHED
        self.shelf_repo.update(entry)
        self.db.commit()
        return BookshelfResponse.model_validate(entry)

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
        """获取书架列表"""
        entries = self.shelf_repo.get_shelf(child_id)
        results = []
        for e in entries:
            resp = BookshelfResponse(
                id=e.id,
                child_id=e.child_id,
                book_id=e.book_id,
                status=e.status,
                book_title=e.book.title if e.book else None,
                book_cover=e.book.cover if e.book else None,
                add_time=e.create_time,
            )
            results.append(resp)
        return results

    def add_favorite(self, child_id: int, book_id: int) -> FavoriteResponse:
        """收藏图书"""
        existing = self.fav_repo.get_by_child_and_book(child_id, book_id)
        if existing:
            return FavoriteResponse(
                id=existing.id,
                child_id=child_id,
                book_id=book_id,
                book_title=existing.book.title if existing.book else None,
                book_cover=existing.book.cover if existing.book else None,
                create_time=existing.create_time,
            )

        fav = Favorites(child_id=child_id, book_id=book_id)
        created = self.fav_repo.create(fav)
        self.db.commit()
        return FavoriteResponse(
            id=created.id,
            child_id=child_id,
            book_id=book_id,
            create_time=created.create_time,
        )

    def get_favorites(self, child_id: int) -> list[FavoriteResponse]:
        """获取收藏夹"""
        favs = self.fav_repo.get_favorites(child_id)
        results = []
        for f in favs:
            results.append(
                FavoriteResponse(
                    id=f.id,
                    child_id=f.child_id,
                    book_id=f.book_id,
                    book_title=f.book.title if f.book else None,
                    book_cover=f.book.cover if f.book else None,
                    create_time=f.create_time,
                )
            )
        return results

    def remove_favorite(self, child_id: int, book_id: int) -> dict:
        """移除收藏"""
        fav = self.fav_repo.get_by_child_and_book(child_id, book_id)
        if not fav:
            raise NotFoundError("未收藏该书")
        self.db.delete(fav)
        self.db.commit()
        return {"status": "unfavorited"}
