# backend/domain/vocabulary/repository.py
"""词汇域数据访问层"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.vocabulary.models import DictionaryWord, UserVocabulary


class DictionaryWordRepository(BaseRepository[DictionaryWord]):
    def __init__(self, db: Session):
        super().__init__(db, DictionaryWord)

    def get_by_word(self, word: str) -> DictionaryWord | None:
        return self.get_by_field("word", word.lower())


class UserVocabularyRepository(BaseRepository[UserVocabulary]):
    def __init__(self, db: Session):
        super().__init__(db, UserVocabulary)

    def get_by_child_and_word(
        self, child_id: int, word_id: int
    ) -> UserVocabulary | None:
        return (
            self.db.query(UserVocabulary)
            .filter(
                UserVocabulary.child_id == child_id,
                UserVocabulary.word_id == word_id,
            )
            .first()
        )

    def get_by_child(
        self, child_id: int, status: int | None = None, sort_by: str = "time"
    ) -> list[UserVocabulary]:
        q = self.db.query(UserVocabulary).filter(UserVocabulary.child_id == child_id)
        if status is not None:
            q = q.filter(UserVocabulary.status == status)
        if sort_by == "alpha":
            q = q.join(DictionaryWord).order_by(DictionaryWord.word)
        else:
            q = q.order_by(UserVocabulary.create_time.desc())
        return q.all()

    def count_by_status(self, child_id: int, status: int) -> int:
        return self.count(child_id=child_id, status=status)
