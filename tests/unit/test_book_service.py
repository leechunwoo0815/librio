# tests/unit/test_book_service.py
"""
[What] 图书服务单元测试
[Why] TDD：先写失败测试
[How] 测试图书搜索、预约等功能
"""

import pytest
from unittest.mock import MagicMock
from backend.services.book_service import BookService
from backend.schemas.book import BookSearch


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def book_service(mock_repo):
    return BookService(mock_repo)


def test_search_books(book_service, mock_repo):
    """
    [What] 测试图书搜索
    [Why] 验证搜索逻辑
    [How] Mock仓库层，测试搜索结果
    """
    search_params = BookSearch(keyword="Charlotte", ar_level="AR1-AR3")
    mock_book = MagicMock(
        id=1, isbn="978-0-06-112495-3", title="Charlotte's Web",
        author="E.B. White", publisher="HarperCollins",
        ar_value=3.2, lexile_value=680, age_min=6, age_max=12,
        theme="friendship", summary="A story about a pig and a spider",
        cover="http://example.com/cover.jpg", total_pages=184,
        create_time="2024-01-01T00:00:00"
    )
    mock_repo.search.return_value = ([mock_book], 1)

    results = book_service.search_books(search_params)

    assert results.total == 1
    assert len(results.items) == 1
    assert results.items[0].title == "Charlotte's Web"


def test_get_book_detail(book_service, mock_repo):
    """
    [What] 测试获取图书详情
    [Why] 验证详情查询逻辑
    [How] Mock仓库层，测试详情返回
    """
    mock_repo.get_by_id.return_value = MagicMock(
        id=1, isbn="978-0-06-112495-3",
        title="Charlotte's Web", author="E.B. White",
        publisher="HarperCollins", ar_value=3.2, lexile_value=680,
        age_min=6, age_max=12, theme="friendship",
        summary="A story about a pig and a spider",
        cover="http://example.com/cover.jpg", total_pages=184,
        create_time="2024-01-01T00:00:00"
    )

    result = book_service.get_book_detail(book_id=1)

    assert result is not None
    assert result.title == "Charlotte's Web"


def test_search_books_invalid_ar_level(book_service, mock_repo):
    """
    [What] 测试无效AR等级格式不会崩溃
    [Why] 验证异常输入的容错处理
    [How] 传入无效ar_level，确保不抛异常
    """
    search_params = BookSearch(keyword="test", ar_level="AR-1")
    mock_repo.search.return_value = ([], 0)

    results = book_service.search_books(search_params)

    assert results.total == 0
    mock_repo.search.assert_called_once()


def test_get_book_detail_not_found(book_service, mock_repo):
    """
    [What] 测试获取不存在的图书详情
    [Why] 验证异常处理
    [How] Mock返回None
    """
    mock_repo.get_by_id.return_value = None

    result = book_service.get_book_detail(book_id=999)

    assert result is None
