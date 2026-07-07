# tests/unit/test_v2_book_extension.py
"""
[What] V2.0 Book模型扩展测试
[Why] TDD: 验证Book新增阅读相关字段
[How] 使用SQLite内存数据库
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.book.models import Book


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_book_v2_fields(db_session):
    """验证Book的V2.0新增字段"""
    book = Book(
        isbn="9780064400558", title="Charlotte's Web", author="E.B. White",
        ar_value=3.2, age_min=7, age_max=9,
        word_count=32000,
        estimated_reading_minutes=45,
        has_audio=1,
        audio_url="https://audio.example.com/charlotte.mp3",
        series_name="Charlotte系列",
        difficulty_level="初级",
    )
    db_session.add(book)
    db_session.commit()

    assert book.word_count == 32000
    assert book.estimated_reading_minutes == 45
    assert book.has_audio == 1
    assert book.audio_url == "https://audio.example.com/charlotte.mp3"
    assert book.series_name == "Charlotte系列"
    assert book.difficulty_level == "初级"


def test_book_v2_defaults(db_session):
    """验证V2.0字段默认值"""
    book = Book(
        isbn="9780000000001", title="Test", author="Author",
        ar_value=1.0, age_min=5, age_max=7,
    )
    db_session.add(book)
    db_session.commit()

    assert book.word_count is None
    assert book.estimated_reading_minutes is None
    assert book.has_audio == 0  # 默认无音频
    assert book.series_name is None
    assert book.difficulty_level is None
