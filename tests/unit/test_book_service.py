# tests/unit/test_book_service.py
"""
[What] 图书服务单元测试
[Why] TDD：先写失败测试
[How] 测试图书搜索、详情等功能
"""

import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.book.models import Book
from backend.domain.book.service import BookService
from backend.domain.book.schemas import BookSearch


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def book_service(db):
    return BookService(db)


def test_search_books(book_service, db):
    """测试图书搜索"""
    for i in range(3):
        db.add(Book(
            isbn=f"97800{i}", title=f"Book {i}", author="Author",
            ar_value=Decimal("2.0"), age_min=5, age_max=9, word_count=1000,
        ))
    db.commit()

    search_params = BookSearch(keyword="Book", page=1, page_size=10)
    result = book_service.search_books(search_params)

    assert result.total == 3
    assert result.page == 1
    assert len(result.items) == 3


def test_get_book_detail(book_service, db):
    """测试获取图书详情"""
    book = Book(isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
                ar_value=Decimal("3.2"), age_min=7, age_max=9, word_count=31000)
    db.add(book); db.commit()

    result = book_service.get_book_detail(book.id)

    assert result is not None
    assert result.title == "Charlotte's Web"
    assert result.author == "E.B. White"


def test_get_book_detail_not_found(book_service, db):
    """测试获取不存在的图书详情"""
    from backend.common.exceptions import NotFoundError
    with pytest.raises(NotFoundError):
        book_service.get_book_detail(999)
