"""批次5 F-116 回归：toggle_publish 下架后用户端搜索/推荐/详情均不可见"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.exceptions import NotFoundError
from backend.database import Base
from backend.domain.book.models import Book
from backend.domain.book.schemas import BookSearch
from backend.domain.book.service import BookService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_book(db, title, isbn, theme="故事", is_published=1):
    b = Book(
        isbn=isbn,
        title=title,
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        theme=theme,
        is_published=is_published,
    )
    db.add(b)
    db.commit()
    return b


class TestF116UserInvisibleAfterPublishOff:
    def test_search_excludes_unpublished(self, db):
        _mk_book(db, "上架书", "9780000001161", is_published=1)
        _mk_book(db, "下架书", "9780000001162", is_published=0)
        result = BookService(db).search_books(BookSearch(keyword="书"))
        books = result.items
        total = result.total
        titles = {b.title for b in books}
        assert "下架书" not in titles
        assert "上架书" in titles
        assert total == 1

    def test_detail_unpublished_404(self, db):
        off = _mk_book(db, "下架详情", "9780000001163", is_published=0)
        with pytest.raises(NotFoundError, match="已下架"):
            BookService(db).get_book_detail(off.id)

    def test_related_excludes_unpublished(self, db):
        on = _mk_book(db, "推荐上架", "9780000001164", theme="科普", is_published=1)
        _mk_book(db, "推荐下架", "9780000001165", theme="科普", is_published=0)
        related = BookService(db).get_related_books(on.id)
        assert all(b.is_published == 1 for b in related)

    def test_toggle_off_hides_detail(self, db):
        b = _mk_book(db, "待下架", "9780000001166", is_published=1)
        svc = BookService(db)
        result = svc.toggle_publish(b.id)
        assert result["is_published"] == 0
        with pytest.raises(NotFoundError, match="已下架"):
            svc.get_book_detail(b.id)


class TestF116AdminListIncludesUnpublished:
    """F-116 终审闭环：管理端列表必须包含下架书（否则无法定位并重新上架）"""

    def test_service_admin_search_includes_unpublished(self, db):
        _mk_book(db, "上架书", "9780000001171", is_published=1)
        _mk_book(db, "下架书", "9780000001172", is_published=0)
        result = BookService(db).search_books(
            BookSearch(keyword="书"), published_only=False
        )
        titles = {b.title for b in result.items}
        assert "下架书" in titles
        assert "上架书" in titles
        assert result.total == 2

    def test_admin_router_uses_admin_query(self, db):
        """直接调用 admin 列表路由：下架书可见（撤 router 传参即红）"""
        from unittest.mock import MagicMock

        from backend.domain.admin.services.book_service import AdminBookService
        from backend.domain.admin.routers.admin_books_router import list_books

        _mk_book(db, "上架书", "9780000001173", is_published=1)
        _mk_book(db, "下架书", "9780000001174", is_published=0)
        resp = list_books(
            keyword="书",
            page=1,
            page_size=20,
            admin=MagicMock(),
            db=db,
            admin_book_service=AdminBookService(db),
        )
        titles = {item["title"] for item in resp["items"]}
        assert "下架书" in titles
        assert "上架书" in titles

    def test_toggle_off_still_visible_in_admin(self, db):
        b = _mk_book(db, "刚下架", "9780000001175", is_published=1)
        svc = BookService(db)
        assert svc.toggle_publish(b.id)["is_published"] == 0
        result = BookService(db).search_books(
            BookSearch(keyword="刚下架"), published_only=False
        )
        assert len(result.items) == 1
        assert result.items[0].title == "刚下架"
        db.expire_all()
        assert db.query(Book).filter(Book.title == "刚下架").first().is_published == 0
