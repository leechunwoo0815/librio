# backend/domain/bookshelf/repository.py
"""书架域数据访问层"""

from sqlalchemy.orm import Session, joinedload

from backend.common.base_repo import BaseRepository
from backend.domain.bookshelf.models import Bookshelf, Favorites
from backend.common.types import BookshelfStatus


class BookshelfRepository(BaseRepository[Bookshelf]):
    """书架仓库"""

    def __init__(self, db: Session):
        super().__init__(db, Bookshelf)

    def get_active_entry(self, child_id: int, book_id: int) -> Bookshelf | None:
        """获取孩子书架中的活跃条目"""
        return (
            self.db.query(Bookshelf)
            .filter(
                Bookshelf.child_id == child_id,
                Bookshelf.book_id == book_id,
                Bookshelf.status == BookshelfStatus.WANT_READ,
                Bookshelf.is_deleted == 0,
            )
            .first()
        )

    def count_active(self, child_id: int) -> int:
        """统计书架活跃条目数"""
        return self.count(child_id=child_id, status=BookshelfStatus.WANT_READ)

    def get_shelf(self, child_id: int) -> list[Bookshelf]:
        """获取孩子书架列表"""
        return (
            self.db.query(Bookshelf)
            .options(joinedload(Bookshelf.book))
            .filter(
                Bookshelf.child_id == child_id,
                Bookshelf.status == BookshelfStatus.WANT_READ,
                Bookshelf.is_deleted == 0,
            )
            .limit(100)
            .all()
        )


class FavoritesRepository(BaseRepository[Favorites]):
    """收藏仓库"""

    def __init__(self, db: Session):
        super().__init__(db, Favorites)

    def get_by_child_and_book(self, child_id: int, book_id: int) -> Favorites | None:
        """查询是否已收藏"""
        return (
            self.db.query(Favorites)
            .filter(
                Favorites.child_id == child_id,
                Favorites.book_id == book_id,
            )
            .first()
        )

    def get_favorites(self, child_id: int) -> list[Favorites]:
        """获取收藏夹"""
        return (
            self.db.query(Favorites)
            .options(joinedload(Favorites.book))
            .filter(Favorites.child_id == child_id, Favorites.is_deleted == 0)
            .limit(100)
            .all()
        )
