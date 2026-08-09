# tests/unit/test_batch2_f119_audio_dedup.py
"""F-119 音频查重回归测试（专家定稿：应用层查重为主，DB 唯一约束对 NULL 不生效）"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ConflictError
from backend.database import Base
from backend.domain.audio.models import AudioFile
from backend.domain.audio.schemas import AudioCreateRequest, AudioUpdateRequest
from backend.domain.audio.service import AudioService
from backend.domain.book.models import Book


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_book(db):
    book = Book(
        title="音频书",
        author="A",
        isbn="9780000000003",
        total_stock=1,
        available_stock=1,
        offline_available=1,
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=100,
    )
    db.add(book)
    db.commit()
    return book


class TestF119AudioDedup:
    def test_create_duplicate_page_rejected(self, db):
        book = _mk_book(db)
        svc = AudioService(db)
        svc.create_audio(
            AudioCreateRequest(
                filename="a.mp3", file_url="/u/a.mp3", book_id=book.id, page_number=1
            )
        )
        with pytest.raises(ConflictError, match="已存在音频"):
            svc.create_audio(
                AudioCreateRequest(
                    filename="b.mp3",
                    file_url="/u/b.mp3",
                    book_id=book.id,
                    page_number=1,
                )
            )

    def test_create_duplicate_null_page_rejected(self, db):
        """全文音频（page_number 皆 NULL）同样唯一"""
        book = _mk_book(db)
        svc = AudioService(db)
        svc.create_audio(
            AudioCreateRequest(filename="a.mp3", file_url="/u/a.mp3", book_id=book.id)
        )
        with pytest.raises(ConflictError, match="已存在音频"):
            svc.create_audio(
                AudioCreateRequest(
                    filename="b.mp3", file_url="/u/b.mp3", book_id=book.id
                )
            )

    def test_update_to_duplicate_rejected(self, db):
        book = _mk_book(db)
        svc = AudioService(db)
        a1 = svc.create_audio(
            AudioCreateRequest(
                filename="a.mp3", file_url="/u/a.mp3", book_id=book.id, page_number=1
            )
        )
        svc.create_audio(
            AudioCreateRequest(
                filename="b.mp3", file_url="/u/b.mp3", book_id=book.id, page_number=2
            )
        )
        with pytest.raises(ConflictError, match="已存在音频"):
            svc.update_audio(
                a1.id,
                AudioUpdateRequest(page_number=2),
            )

    def test_different_pages_allowed(self, db):
        book = _mk_book(db)
        svc = AudioService(db)
        svc.create_audio(
            AudioCreateRequest(
                filename="a.mp3", file_url="/u/a.mp3", book_id=book.id, page_number=1
            )
        )
        svc.create_audio(
            AudioCreateRequest(
                filename="b.mp3", file_url="/u/b.mp3", book_id=book.id, page_number=2
            )
        )
        count = db.query(AudioFile).filter(AudioFile.book_id == book.id).count()
        assert count == 2

    def test_db_unique_backstop_blocks_raw_duplicate(self, db):
        """F-119 终审：DB 生成列唯一兜底——绕过应用层直接插入同 key 必 IntegrityError"""
        from sqlalchemy.exc import IntegrityError

        book = _mk_book(db)
        svc = AudioService(db)
        svc.create_audio(
            AudioCreateRequest(
                filename="a.mp3", file_url="/u/a.mp3", book_id=book.id, page_number=1
            )
        )
        dup = AudioFile(
            filename="c.mp3",
            file_url="/u/c.mp3",
            book_id=book.id,
            page_number=1,
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_soft_deleted_releases_unique_key(self, db):
        """软删后同书同页可重新录入（active_audio_key 置 NULL 释放唯一）"""
        book = _mk_book(db)
        svc = AudioService(db)
        created = svc.create_audio(
            AudioCreateRequest(
                filename="a.mp3", file_url="/u/a.mp3", book_id=book.id, page_number=1
            )
        )
        svc.delete_audio(created.id)
        again = svc.create_audio(
            AudioCreateRequest(
                filename="b.mp3", file_url="/u/b.mp3", book_id=book.id, page_number=1
            )
        )
        assert again.id is not None

    def test_create_db_backstop_returns_conflict_not_500(self, db, monkeypatch):
        """F-119 终审同类：并发窗口内 DB 唯一兜底触发时必须转 ConflictError（409），不得裸 IntegrityError 500"""
        book = _mk_book(db)
        svc = AudioService(db)
        svc.create_audio(
            AudioCreateRequest(
                filename="a.mp3", file_url="/u/a.mp3", book_id=book.id, page_number=1
            )
        )
        # 模拟并发窗口：应用层查重被绕过（另一请求同时通过），DB 唯一索引兜底
        monkeypatch.setattr(
            AudioService, "_find_dup_audio", lambda self, *a, **k: False
        )
        with pytest.raises(ConflictError, match="已存在音频"):
            svc.create_audio(
                AudioCreateRequest(
                    filename="b.mp3",
                    file_url="/u/b.mp3",
                    book_id=book.id,
                    page_number=1,
                )
            )

    def test_update_db_backstop_returns_conflict_not_500(self, db, monkeypatch):
        """F-119 终审同类：update 并发窗口 DB 兜底 → 409 而非 500"""
        book = _mk_book(db)
        svc = AudioService(db)
        a1 = svc.create_audio(
            AudioCreateRequest(
                filename="a.mp3", file_url="/u/a.mp3", book_id=book.id, page_number=1
            )
        )
        svc.create_audio(
            AudioCreateRequest(
                filename="b.mp3", file_url="/u/b.mp3", book_id=book.id, page_number=2
            )
        )
        monkeypatch.setattr(
            AudioService, "_find_dup_audio", lambda self, *a, **k: False
        )
        with pytest.raises(ConflictError, match="已存在音频"):
            svc.update_audio(a1.id, AudioUpdateRequest(page_number=2))
