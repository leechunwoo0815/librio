# tests/unit/test_checkin_vocab_shelf.py
"""批次6 单元测试 — C1 每类型打卡 / C3 查词自动记录 / C4 想读清单限量与标灰"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.database import Base
from backend.common.exceptions import ConflictError
from backend.domain.book.models import Book
from backend.domain.bookshelf.service import BookshelfService
from backend.domain.child.models import Child
from backend.domain.reading.models import CheckIn
from backend.domain.reading.service import ReadingService
from backend.domain.user.models import User
from backend.domain.vocabulary.models import DictionaryWord, UserVocabulary
from backend.domain.vocabulary.service import VocabularyService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_child(db, status=2):
    user = User(openid="cv1", phone="13800000501")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="打卡", age=7, grade="二年级", status=status)
    db.add(child)
    db.commit()
    return user, child


def _mk_book(db, isbn="CV001", stock=3):
    book = Book(
        isbn=isbn,
        title="书",
        author="A",
        ar_value=Decimal("2.0"),
        age_min=5,
        age_max=9,
        word_count=1000,
        total_stock=stock,
        available_stock=stock,
    )
    db.add(book)
    db.commit()
    return book


class TestCheckinPerType:
    """C1：每种类型每日各 1 次"""

    def test_same_type_dedup_different_type_allowed(self, db):
        _, child = _mk_child(db)
        svc = ReadingService(db)
        svc._check_auto_checkin(child.id, duration_seconds=660, words_read=10)
        svc._check_auto_checkin(child.id, duration_seconds=660, words_read=10)  # 重复
        svc._check_voice_checkin(child.id)
        svc._check_voice_checkin(child.id)  # 重复
        db.commit()

        rows = (
            db.query(CheckIn)
            .filter(CheckIn.child_id == child.id, CheckIn.check_date == date.today())
            .all()
        )
        assert len(rows) == 2
        types = {r.check_type for r in rows}
        assert types == {CheckIn.TYPE_READING, CheckIn.TYPE_VOICE}

    def test_daily_cap_4(self, db):
        """总上限 4 次/天（4 种类型）"""
        _, child = _mk_child(db)
        svc = ReadingService(db)
        svc._check_auto_checkin(child.id, duration_seconds=660, words_read=10)
        svc._check_voice_checkin(child.id)
        vocab_svc = VocabularyService(db)
        dw = DictionaryWord(word="apple", chinese_meaning="苹果")
        db.add(dw)
        db.commit()
        vocab_svc.record_lookup(child.id, "apple")  # TYPE_VOCABULARY
        # 手动补一条读完类型，凑满 4 条
        db.add(
            CheckIn(
                child_id=child.id,
                check_date=date.today(),
                check_type=CheckIn.TYPE_FINISH_BOOK,
            )
        )
        db.commit()
        # 第 5 次任何类型都被总上限拦截
        svc._check_auto_checkin(child.id, duration_seconds=660, words_read=10)
        count = (
            db.query(CheckIn)
            .filter(CheckIn.child_id == child.id, CheckIn.check_date == date.today())
            .count()
        )
        assert count == 4


class TestRecordLookup:
    """C3：查词自动记录生词本"""

    def test_lookup_creates_and_accumulates(self, db):
        _, child = _mk_child(db)
        db.add(DictionaryWord(word="curiosity", chinese_meaning="好奇心"))
        db.commit()
        svc = VocabularyService(db)

        svc.record_lookup(child.id, "curiosity")
        svc.record_lookup(child.id, "curiosity")

        uv = db.query(UserVocabulary).filter(UserVocabulary.child_id == child.id).one()
        assert uv.lookup_count == 2

    def test_lookup_triggers_vocab_checkin_once(self, db):
        _, child = _mk_child(db)
        db.add(DictionaryWord(word="banana", chinese_meaning="香蕉"))
        db.commit()
        svc = VocabularyService(db)
        svc.record_lookup(child.id, "banana")
        svc.record_lookup(child.id, "banana")  # 第二次不重复打卡
        count = (
            db.query(CheckIn)
            .filter(
                CheckIn.child_id == child.id,
                CheckIn.check_type == CheckIn.TYPE_VOCABULARY,
            )
            .count()
        )
        assert count == 1


class TestShelfLimitAndStock:
    """C4：限 100 本 + 无库存标灰"""

    def test_limit_100(self, db):
        _, child = _mk_child(db)
        svc = BookshelfService(db)
        for i in range(100):
            book = _mk_book(db, isbn=f"CV{i:05d}")
            svc.add_to_shelf(child.id, book.id)
        extra = _mk_book(db, isbn="CVEXTRA")
        with pytest.raises(ConflictError, match="书架已满"):
            svc.add_to_shelf(child.id, extra.id)

    def test_get_shelf_includes_stock_flag(self, db):
        _, child = _mk_child(db)
        svc = BookshelfService(db)
        book = _mk_book(db, stock=0)
        svc.add_to_shelf(child.id, book.id)
        shelf = svc.get_shelf(child.id)
        assert shelf[0].in_stock is False
        assert shelf[0].available_stock == 0
