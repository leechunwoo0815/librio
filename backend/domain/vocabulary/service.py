# backend/domain/vocabulary/service.py
"""词汇域业务逻辑 — 查词、生词本管理"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend.common.exceptions import ValidationError
from backend.domain.vocabulary.models import UserVocabulary
from backend.domain.vocabulary.repository import (
    DictionaryWordRepository,
    UserVocabularyRepository,
)

logger = logging.getLogger(__name__)


class VocabularyService:
    def __init__(self, db: Session):
        self.db = db
        self.dict_repo = DictionaryWordRepository(db)
        self.vocab_repo = UserVocabularyRepository(db)

    def lookup_word(self, word: str) -> dict | None:
        w = self.dict_repo.get_by_word(word.lower())
        if not w:
            return None
        return {
            "id": w.id,
            "word": w.word,
            "phonetic": w.phonetic,
            "audio_url": w.audio_url,
            "part_of_speech": w.part_of_speech,
            "chinese_meaning": w.chinese_meaning,
            "example_sentence": w.example_sentence,
            "level": w.level,
        }

    def add_to_vocabulary(
        self, child_id: int, word=None, book_id=None, **kwargs
    ) -> dict:
        if not word and "word" in kwargs:
            word = kwargs["word"]
        word_lower = word.lower()
        dw = self.dict_repo.get_by_word(word_lower)
        if not dw:
            raise ValidationError(f"词典中未收录该单词: {word_lower}")

        existing = self.vocab_repo.get_by_child_and_word(child_id, dw.id)
        if existing:
            existing.lookup_count += 1
            existing.last_review_time = datetime.now()
            self.vocab_repo.update(existing)
            self.db.commit()
            return {
                "id": existing.id,
                "word": dw.word,
                "phonetic": dw.phonetic,
                "chinese_meaning": dw.chinese_meaning,
                "status": existing.status,
                "lookup_count": existing.lookup_count,
                "is_new": False,
            }

        uv = UserVocabulary(
            child_id=child_id,
            word_id=dw.id,
            book_id=book_id,
            lookup_count=1,
            last_review_time=datetime.now(),
        )
        created = self.vocab_repo.create(uv)
        self.db.commit()
        logger.info(f"Vocab added: child={child_id}, word={dw.word}")
        return {
            "id": created.id,
            "word": dw.word,
            "phonetic": dw.phonetic,
            "chinese_meaning": dw.chinese_meaning,
            "status": created.status,
            "lookup_count": 1,
            "is_new": True,
        }

    def mark_mastered(self, vocab_id: int) -> dict:
        uv = self.vocab_repo.get_by_id_or_raise(vocab_id)
        uv.status = UserVocabulary.STATUS_MASTERED
        self.vocab_repo.update(uv)
        self.db.commit()
        return {"id": uv.id, "status": "mastered"}

    def remove_from_vocabulary(self, vocab_id: int) -> dict:
        """从生词本移除（软删除）"""
        self.vocab_repo.get_by_id_or_raise(vocab_id)  # 验证存在
        self.vocab_repo.soft_delete(vocab_id)
        self.db.commit()
        logger.info(f"Vocab removed: id={vocab_id}")
        return {"id": vocab_id, "removed": True}

    def get_vocabulary_list(
        self, child_id: int, status=None, sort_by="time"
    ) -> list[dict]:
        results = self.vocab_repo.get_by_child(child_id, status, sort_by)
        return [
            {
                "id": uv.id,
                "word": uv.word.word if uv.word else "",
                "phonetic": uv.word.phonetic if uv.word else "",
                "chinese_meaning": uv.word.chinese_meaning if uv.word else "",
                "status": uv.status,
                "lookup_count": uv.lookup_count,
                "last_review_time": uv.last_review_time.isoformat()
                if uv.last_review_time
                else None,
            }
            for uv in results
        ]

    def get_vocab_stats(self, child_id: int) -> dict:
        learning = self.vocab_repo.count_by_status(
            child_id, UserVocabulary.STATUS_LEARNING
        )
        mastered = self.vocab_repo.count_by_status(
            child_id, UserVocabulary.STATUS_MASTERED
        )
        return {
            "learning": learning,
            "mastered": mastered,
            "total": learning + mastered,
        }

    def check_lookup_allowed(self, user_id: int) -> None:
        """检查查词是否允许（开关 + 次数限制）。不允许时抛出 ForbiddenError。"""
        from backend.common.config_service import ConfigService
        from backend.common.types import MemberStatus
        from backend.common.exceptions import ForbiddenError
        from backend.domain.child.models import Child

        # 检查查词开关
        enabled = ConfigService.get_bool(self.db, "enable_vocab_lookup", True)
        if not enabled:
            raise ForbiddenError("查词功能已关闭")

        # 检查查词次数限制（仅 TRIAL 用户）
        child = (
            self.db.query(Child)
            .filter(Child.user_id == user_id, Child.is_deleted == 0)
            .first()
        )
        if child and child.status == MemberStatus.TRIAL:
            limit = ConfigService.get_int(self.db, "vocab_lookup_limit", 10)
            today_count = self.get_today_lookup_count(user_id)
            if today_count >= limit:
                raise ForbiddenError(f"试读用户每日查词上限 {limit} 次，请升级会员")

    def get_today_lookup_count(self, user_id: int) -> int:
        """统计用户今日查词次数（基于孩子的生词本 last_review_time）"""
        from backend.domain.child.models import Child

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        children = (
            self.db.query(Child)
            .filter(Child.user_id == user_id, Child.is_deleted == 0)
            .all()
        )
        if not children:
            return 0
        child_ids = [c.id for c in children]
        count = (
            self.db.query(UserVocabulary)
            .filter(
                UserVocabulary.child_id.in_(child_ids),
                UserVocabulary.last_review_time >= today_start,
                UserVocabulary.is_deleted == 0,
            )
            .count()
        )
        return count
