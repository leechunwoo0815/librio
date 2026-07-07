# tests/unit/test_vocabulary_service.py
"""
[What] V2.0 词汇服务单元测试
[Why] TDD: 验证查词、生词本CRUD、复习功能
[How] Mock数据库会话
"""

import pytest
from unittest.mock import MagicMock
from backend.domain.vocabulary.service import VocabularyService
from backend.domain.vocabulary.models import DictionaryWord, UserVocabulary
from datetime import datetime


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def vocab_service(mock_db):
    return VocabularyService(mock_db)


def test_lookup_word_found(vocab_service, mock_db):
    """查词命中"""
    mock_word = MagicMock()
    mock_word.id = 1
    mock_word.word = "curiosity"
    mock_word.chinese_meaning = "好奇心"
    mock_word.phonetic = "/ˌkjʊriˈɑːsəti/"
    mock_word.part_of_speech = "名词"
    mock_word.example_sentence = "Curiosity killed the cat."
    mock_db.query.return_value.filter.return_value.first.return_value = mock_word

    result = vocab_service.lookup_word("curiosity")
    assert result["word"] == "curiosity"
    assert result["chinese_meaning"] == "好奇心"


def test_lookup_word_not_found(vocab_service, mock_db):
    """查词未命中"""
    mock_db.query.return_value.filter.return_value.first.return_value = None
    result = vocab_service.lookup_word("unknownword")
    assert result is None


def test_add_to_vocabulary_new(vocab_service, mock_db):
    """添加生词——首次"""
    mock_word = MagicMock()
    mock_word.id = 1
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_word,   # dictionary_word found
        None,        # user_vocabulary not exists yet
    ]

    mock_uv = MagicMock()
    mock_uv.id = 1
    mock_uv.word_id = 1
    mock_uv.status = UserVocabulary.STATUS_LEARNING
    mock_db.add.return_value = None

    result = vocab_service.add_to_vocabulary(child_id=1, word="curiosity", book_id=1)
    assert result is not None


def test_add_to_vocabulary_already_exists(vocab_service, mock_db):
    """添加生词——已存在，增加查询次数"""
    mock_word = MagicMock()
    mock_word.id = 1
    mock_uv = MagicMock()
    mock_uv.lookup_count = 2
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_word,   # dictionary_word found
        mock_uv,     # user_vocabulary exists
    ]

    result = vocab_service.add_to_vocabulary(child_id=1, word="curiosity")
    assert mock_uv.lookup_count == 3  # incremented


def test_mark_mastered(vocab_service, mock_db):
    """标记生词已掌握"""
    mock_uv = MagicMock()
    mock_uv.status = UserVocabulary.STATUS_LEARNING
    mock_db.query.return_value.filter.return_value.first.return_value = mock_uv

    result = vocab_service.mark_mastered(vocab_id=1)
    assert mock_uv.status == UserVocabulary.STATUS_MASTERED


def test_get_vocabulary_list(vocab_service, mock_db):
    """获取生词列表"""
    mock_uv = MagicMock()
    mock_uv.id = 1
    mock_uv.word_id = 1
    mock_uv.status = 0
    mock_uv.lookup_count = 3
    mock_uv.last_review_time = datetime.now()
    mock_uv.create_time = datetime.now()
    mock_uv.word = MagicMock()
    mock_uv.word.word = "curiosity"
    mock_uv.word.chinese_meaning = "好奇心"
    mock_uv.word.phonetic = "/ˌkjʊriˈɑːsəti/"

    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_uv]

    result = vocab_service.get_vocabulary_list(child_id=1)
    assert len(result) == 1
    assert result[0]["word"] == "curiosity"


def test_get_vocab_stats(vocab_service, mock_db):
    """生词统计"""
    vocab_service.vocab_repo.count_by_status = MagicMock(side_effect=[47, 23])

    result = vocab_service.get_vocab_stats(child_id=1)
    assert result["learning"] == 47
    assert result["mastered"] == 23
    assert result["total"] == 70
