# backend/domain/advancement/repository.py
"""晋级域数据访问层"""

from sqlalchemy.orm import Session, joinedload

from backend.common.base_repo import BaseRepository
from backend.domain.advancement.models import (
    Level,
    ChildLevel,
    QuestionBank,
    Quiz,
    QuizAnswer,
    Achievement,
    ChildAchievement,
)


class LevelRepository(BaseRepository[Level]):
    def __init__(self, db: Session):
        super().__init__(db, Level)

    def get_all_ordered(self) -> list[Level]:
        return (
            self.db.query(Level)
            .filter(Level.is_deleted == 0)
            .order_by(Level.sort_order)
            .all()
        )


class ChildLevelRepository(BaseRepository[ChildLevel]):
    def __init__(self, db: Session):
        super().__init__(db, ChildLevel)

    def get_current(self, child_id: int) -> ChildLevel | None:
        return (
            self.db.query(ChildLevel)
            .filter(
                ChildLevel.child_id == child_id,
                ChildLevel.is_current,
                ChildLevel.is_deleted == 0,
            )
            .first()
        )


class QuestionBankRepository(BaseRepository[QuestionBank]):
    def __init__(self, db: Session):
        super().__init__(db, QuestionBank)

    def get_by_book(self, book_id: int, limit: int = 5) -> list[QuestionBank]:
        from sqlalchemy import func

        return (
            self.db.query(QuestionBank)
            .filter(
                QuestionBank.book_id == book_id,
                QuestionBank.is_deleted == 0,
            )
            .order_by(func.random())
            .limit(limit)
            .all()
        )


class QuizRepository(BaseRepository[Quiz]):
    def __init__(self, db: Session):
        super().__init__(db, Quiz)


class QuizAnswerRepository(BaseRepository[QuizAnswer]):
    def __init__(self, db: Session):
        super().__init__(db, QuizAnswer)

    def get_by_quiz(self, quiz_id: int) -> list[QuizAnswer]:
        return self.list_all(limit=50, quiz_id=quiz_id)


class AchievementRepository(BaseRepository[Achievement]):
    def __init__(self, db: Session):
        super().__init__(db, Achievement)


class ChildAchievementRepository(BaseRepository[ChildAchievement]):
    def __init__(self, db: Session):
        super().__init__(db, ChildAchievement)

    def get_by_child(self, child_id: int) -> list[ChildAchievement]:
        return (
            self.db.query(ChildAchievement)
            .options(joinedload(ChildAchievement.achievement))
            .filter(
                ChildAchievement.child_id == child_id, ChildAchievement.is_deleted == 0
            )
            .limit(100)
            .all()
        )

    def has_achievement(self, child_id: int, achievement_id: int) -> bool:
        return self.exists(child_id=child_id, achievement_id=achievement_id)
