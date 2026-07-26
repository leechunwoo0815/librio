# backend/domain/bookshelf/repository.py
"""书架域数据访问层"""

from sqlalchemy.orm import Session, joinedload

from backend.common.base_repo import BaseRepository
from backend.domain.bookshelf.models import Bookshelf
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
        """获取孩子书架列表（想读+已读完，排除手动移除）"""
        return (
            self.db.query(Bookshelf)
            .options(joinedload(Bookshelf.book))
            .filter(
                Bookshelf.child_id == child_id,
                Bookshelf.status != BookshelfStatus.REMOVED,
                Bookshelf.is_deleted == 0,
            )
            .limit(100)
            .all()
        )
