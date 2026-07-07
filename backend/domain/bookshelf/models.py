# backend/domain/bookshelf/models.py
"""书架域模型 — 想读清单 + 收藏夹

V3.1 关键变更：
  Bookshelf = 想读清单，容量无限，与借阅无关！
  旧代码把 Bookshelf 当成借阅书架（STATUS_BORROWING + 20本上限），这是错误的。
  借阅功能已移至 domain/borrow/ 的 BorrowRecord。
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, SmallInteger
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel
from backend.common.types import BookshelfStatus


class Bookshelf(BaseModel):
    """想读清单 — V3.1: 与借阅无关，纯收藏性质

    容量无限。孩子可以加入任何想读的书。
    读完的书状态变为 FINISHED（由事件自动更新）。
    手动移除变为 REMOVED。
    """

    __tablename__ = "bookshelf"
    __table_args__ = {"extend_existing": True}

    # 向后兼容常量（旧测试/旧代码使用）
    STATUS_BORROWING = BookshelfStatus.WANT_READ  # 0 = 想读
    STATUS_RETURNED = BookshelfStatus.FINISHED  # 1 = 已读完

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, index=True, comment="图书ID"
    )
    status = Column(
        SmallInteger,
        default=BookshelfStatus.WANT_READ,
        comment="状态: 0=想读 1=已读完 2=移除",
    )
    added_time = Column(DateTime, nullable=True, comment="加入时间")

    # 关系
    child = relationship("Child", foreign_keys=[child_id])
    book = relationship("Book", foreign_keys=[book_id])

    def __repr__(self):
        return f"<Bookshelf(child={self.child_id}, book={self.book_id}, status={self.status})>"


class Favorites(BaseModel):
    """收藏夹 — 不限量"""

    __tablename__ = "favorites"
    __table_args__ = {"extend_existing": True}

    child_id = Column(
        BigInteger, ForeignKey("child.id"), nullable=False, index=True, comment="孩子ID"
    )
    book_id = Column(
        BigInteger, ForeignKey("book.id"), nullable=False, comment="图书ID"
    )

    # 关系
    child = relationship("Child", foreign_keys=[child_id])
    book = relationship("Book", foreign_keys=[book_id])
