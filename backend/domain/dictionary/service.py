# backend/domain/dictionary/service.py
"""词库域业务逻辑"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.domain.vocabulary.models import DictionaryWord
from backend.domain.dictionary.schemas import (
    WordCreateRequest,
    WordUpdateRequest,
    WordResponse,
    WordListResponse,
)
from backend.common.exceptions import NotFoundError, ValidationError


class DictionaryService:
    """词库服务"""

    def __init__(self, db: Session):
        self.db = db

    def search_words(
        self,
        keyword: str | None = None,
        level: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> WordListResponse:
        """搜索单词"""
        query = self.db.query(DictionaryWord).filter(DictionaryWord.is_deleted == 0)

        if keyword:
            query = query.filter(
                (DictionaryWord.word.contains(keyword))
                | (DictionaryWord.chinese_meaning.contains(keyword))
            )
        if level:
            query = query.filter(DictionaryWord.level == level)

        total = query.count()
        items = (
            query.order_by(DictionaryWord.word)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        result = []
        for w in items:
            result.append(
                WordResponse(
                    id=w.id,
                    word=w.word,
                    phonetic=w.phonetic,
                    pos=w.part_of_speech,
                    cn_definition=w.chinese_meaning,
                    example_sentence=w.example_sentence,
                    ar_level=w.level,
                    create_time=w.create_time,
                )
            )

        return WordListResponse(
            items=result, total=total, page=page, page_size=page_size
        )

    def get_word(self, word_id: int) -> WordResponse:
        """获取单词详情"""
        w = (
            self.db.query(DictionaryWord)
            .filter(DictionaryWord.id == word_id, DictionaryWord.is_deleted == 0)
            .first()
        )
        if not w:
            raise NotFoundError("单词不存在")

        return WordResponse(
            id=w.id,
            word=w.word,
            phonetic=w.phonetic,
            pos=w.part_of_speech,
            cn_definition=w.chinese_meaning,
            example_sentence=w.example_sentence,
            ar_level=w.level,
            create_time=w.create_time,
        )

    def create_word(self, data: WordCreateRequest) -> WordResponse:
        """创建单词"""
        # 检查单词是否已存在
        existing = (
            self.db.query(DictionaryWord)
            .filter(DictionaryWord.word == data.word.lower())
            .first()
        )
        if existing:
            raise ValidationError(f"单词 '{data.word}' 已存在")

        word = DictionaryWord(
            word=data.word.lower(),
            phonetic=data.phonetic,
            part_of_speech=data.pos,
            chinese_meaning=data.cn_definition or "",
            example_sentence=data.example_sentence,
            level=data.ar_level,
        )
        self.db.add(word)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValidationError(f"单词 '{data.word}' 已存在（并发创建）")
        self.db.refresh(word)

        return self.get_word(word.id)

    def update_word(self, word_id: int, data: WordUpdateRequest) -> WordResponse:
        """更新单词"""
        word = (
            self.db.query(DictionaryWord).filter(DictionaryWord.id == word_id).first()
        )
        if not word:
            raise NotFoundError("单词不存在")

        if data.word is not None:
            word.word = data.word.lower()
        if data.phonetic is not None:
            word.phonetic = data.phonetic
        if data.pos is not None:
            word.part_of_speech = data.pos
        if data.cn_definition is not None:
            word.chinese_meaning = data.cn_definition
        if data.example_sentence is not None:
            word.example_sentence = data.example_sentence
        if data.ar_level is not None:
            word.level = data.ar_level

        self.db.commit()
        return self.get_word(word_id)

    def delete_word(self, word_id: int) -> dict:
        """删除单词（软删除）"""
        word = (
            self.db.query(DictionaryWord)
            .filter(DictionaryWord.id == word_id, DictionaryWord.is_deleted == 0)
            .first()
        )
        if not word:
            raise NotFoundError("单词不存在")

        word.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "单词已删除"}
