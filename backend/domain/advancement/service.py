# backend/domain/advancement/service.py
"""晋级域业务逻辑 — 级别管理、测验评分、晋级检测、成就授予

排行榜已拆分到 LeaderboardService（独立查询域，无写操作）。
向后兼容方法已删除。
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.events import (
    QuizPassedEvent,
    QuizFailedEvent,
    LevelAdvancedEvent,
    event_bus,
)
from backend.common.exceptions import ConflictError, NotFoundError
from backend.domain.advancement.models import (
    Level,
    ChildLevel,
    QuestionBank,
    Quiz,
    QuizAnswer,
    ChildAchievement,
)
from backend.domain.advancement.repository import (
    LevelRepository,
    ChildLevelRepository,
    QuestionBankRepository,
    QuizRepository,
    QuizAnswerRepository,
    AchievementRepository,
    ChildAchievementRepository,
)
from backend.domain.advancement.schemas import (
    LevelResponse,
    ChildLevelResponse,
    QuizStartRequest,
    QuizResponse,
    QuestionResponse,
    AchievementResponse,
    ChildAchievementResponse,
)
from backend.domain.book.models import Book
from backend.common.types import PASS_THRESHOLD
from backend.common.config_service import ConfigService

logger = logging.getLogger(__name__)


class AdvancementService:
    """晋级服务 — 级别 + 测验 + 晋级 + 成就"""

    def __init__(self, db: Session):
        self.db = db
        self.level_repo = LevelRepository(db)
        self.child_level_repo = ChildLevelRepository(db)
        self.question_repo = QuestionBankRepository(db)
        self.quiz_repo = QuizRepository(db)
        self.answer_repo = QuizAnswerRepository(db)
        self.achievement_repo = AchievementRepository(db)
        self.child_achievement_repo = ChildAchievementRepository(db)
        self.book_repo = BaseRepository(db, Book)

    # ==================== 级别 ====================

    def get_levels(self) -> list[LevelResponse]:
        return [
            LevelResponse.model_validate(lv) for lv in self.level_repo.get_all_ordered()
        ]

    def get_current_level(self, child_id: int) -> ChildLevelResponse | None:
        cl = self.child_level_repo.get_current(child_id)
        if not cl:
            return None
        resp = ChildLevelResponse.model_validate(cl)
        if cl.level:
            resp.level_name = cl.level.name
        return resp

    # ==================== 测验 ====================

    def start_quiz(self, child_id: int, data: QuizStartRequest) -> QuizResponse:
        """开始测验 — 含可配置重考间隔限制"""
        from datetime import timezone

        questions = self.question_repo.get_by_book(data.book_id)
        if not questions:
            raise NotFoundError("该图书暂无测验题目")

        # 从配置读取测验题数上限
        from backend.common.config_service import ConfigService

        max_questions = ConfigService.get_int(self.db, "quiz_total_questions", 5)
        if len(questions) > max_questions:
            questions = questions[:max_questions]

        # 重考间隔检查：从配置读取冷却分钟数（5-1440，默认60）
        cooldown_minutes = ConfigService.get_int(self.db, "quiz_cooldown_minutes", 60)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        recent_quiz = (
            self.db.query(Quiz)
            .filter(
                Quiz.child_id == child_id,
                Quiz.book_id == data.book_id,
                Quiz.status == Quiz.STATUS_COMPLETED,
                Quiz.create_time > now_utc - timedelta(minutes=cooldown_minutes),
                Quiz.is_deleted == 0,
            )
            .order_by(Quiz.create_time.desc())
            .first()
        )
        if recent_quiz:
            remaining = timedelta(minutes=cooldown_minutes) - (
                now_utc - recent_quiz.create_time
            )
            minutes = int(remaining.total_seconds() / 60)
            raise ConflictError(f"测验冷却中，请 {minutes} 分钟后重试")

        quiz = Quiz(
            child_id=child_id,
            book_id=data.book_id,
            submission_id=data.submission_id,
            total_questions=len(questions),
        )
        created = self.quiz_repo.create(quiz)
        self.db.commit()
        return QuizResponse.model_validate(created)

    def get_quiz_questions(
        self, book_or_quiz_id: int, is_quiz_id: bool = False
    ) -> list:
        """获取题目列表"""
        if is_quiz_id:
            quiz = self.quiz_repo.get_by_id(book_or_quiz_id)
            if not quiz:
                return []
            questions = self.question_repo.get_by_book(quiz.book_id)
        else:
            questions = self.question_repo.get_by_book(book_or_quiz_id)
        return [
            {
                "id": q.id,
                "question_text": q.question_text,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "difficulty": q.difficulty,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
            }
            for q in questions
        ]

    def submit_answers(self, quiz_id: int, answers: list) -> dict:
        """提交测验答案 — 评分 + 发布事件"""
        quiz = (
            self.db.query(Quiz)
            .filter(Quiz.id == quiz_id, Quiz.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not quiz:
            raise NotFoundError("测验不存在")

        if quiz.status != Quiz.STATUS_IN_PROGRESS:
            raise ConflictError("测验已结束")

        correct = 0
        qids = [
            (ans["question_id"] if isinstance(ans, dict) else ans.question_id)
            for ans in answers
        ]
        questions = {
            q.id: q
            for q in self.db.query(QuestionBank).filter(QuestionBank.id.in_(qids)).all()
        }
        for ans in answers:
            if isinstance(ans, dict):
                qid = ans["question_id"]
                selected = ans.get("answer") or ans.get("selected_answer")
            else:
                qid = ans.question_id
                selected = ans.selected_answer

            question = questions.get(qid)
            is_correct = question and question.correct_answer == selected
            if is_correct:
                correct += 1

            answer_record = QuizAnswer(
                quiz_id=quiz_id,
                question_id=qid,
                selected_answer=selected,
                is_correct=is_correct,
            )
            self.answer_repo.create(answer_record)

        quiz.correct_count = correct
        quiz.score = Decimal(
            str(round(correct / max(quiz.total_questions, 1) * 100, 2))
        )
        quiz.status = Quiz.STATUS_COMPLETED
        self.quiz_repo.update(quiz)

        pass_rate = ConfigService.get_decimal(self.db, "quiz_pass_rate", PASS_THRESHOLD)
        passed = quiz.score >= pass_rate * 100

        book = self.book_repo.get_by_id(quiz.book_id)
        word_count = book.word_count if book else 0
        effective_word_count = word_count

        if passed:
            # P0-8: 去重条件改为"存在其他已通过的 Quiz"（而非任意已完成）
            pass_threshold = pass_rate * 100
            already_counted = (
                self.db.query(Quiz)
                .filter(
                    Quiz.child_id == quiz.child_id,
                    Quiz.book_id == quiz.book_id,
                    Quiz.status == Quiz.STATUS_COMPLETED,
                    Quiz.score >= pass_threshold,
                    Quiz.id != quiz.id,
                    Quiz.is_deleted == 0,
                )
                .first()
            )
            if already_counted:
                effective_word_count = 0

            event_bus.publish(
                QuizPassedEvent(
                    child_id=quiz.child_id,
                    book_id=quiz.book_id,
                    quiz_id=quiz.id,
                    word_count=effective_word_count,
                ),
                db=self.db,
            )
            logger.info(
                f"Quiz passed: child={quiz.child_id}, quiz={quiz_id}, score={quiz.score}"
            )
        else:
            event_bus.publish(
                QuizFailedEvent(
                    child_id=quiz.child_id,
                    book_id=quiz.book_id,
                    quiz_id=quiz.id,
                    score=float(quiz.score),
                ),
                db=self.db,
            )
            logger.info(
                f"Quiz failed: child={quiz.child_id}, quiz={quiz_id}, score={quiz.score}"
            )

        self.db.commit()
        return {
            "correct": correct,
            "total": quiz.total_questions,
            "score": float(quiz.score),
            "passed": passed,
            "word_count": effective_word_count,
        }

    # ==================== 晋级检测 ====================

    def check_and_advance(self, child_id: int) -> ChildLevelResponse | None:
        """晋级检测"""
        current = (
            self.db.query(ChildLevel)
            .filter(
                ChildLevel.child_id == child_id,
                ChildLevel.is_current,
                ChildLevel.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if not current:
            return None

        level = self.level_repo.get_by_id(current.level_id)
        if not level:
            return None

        from backend.common.config_service import ConfigService

        min_quiz_pass = ConfigService.get_int(self.db, "quiz_pass_count", 5)
        if (
            current.books_read_at_level >= level.required_books
            and current.quizzes_passed_at_level >= min_quiz_pass
        ):
            # 需要老师审核时，记录审核请求（不自动晋级）
            # Level 字段优先，否则读全局配置
            need_review = level.require_teacher_review or ConfigService.get_bool(
                self.db, "require_teacher_review", False
            )
            if need_review:
                logger.info(
                    f"Advancement pending review: child={child_id}, level={level.name}"
                )
                return None

            next_level = (
                self.db.query(Level)
                .filter(
                    Level.sort_order > level.sort_order,
                    Level.is_deleted == 0,
                )
                .order_by(Level.sort_order)
                .first()
            )

            if next_level:
                current.is_current = False
                self.child_level_repo.update(current)

                new_cl = ChildLevel(
                    child_id=child_id,
                    level_id=next_level.id,
                    achieved_at=datetime.now(),
                    is_current=True,
                )
                self.child_level_repo.create(new_cl)

                event_bus.publish(
                    LevelAdvancedEvent(
                        child_id=child_id,
                        from_level=level.name,
                        to_level=next_level.name,
                    ),
                    db=self.db,
                )

                self.db.commit()
                logger.info(
                    f"Level advanced: child={child_id}, {level.name} -> {next_level.name}"
                )
                resp = ChildLevelResponse.model_validate(new_cl)
                resp.level_name = next_level.name
                return resp

        return None

    # ==================== 成就 ====================

    def get_achievements(self) -> list[AchievementResponse]:
        return [
            AchievementResponse.model_validate(a)
            for a in self.achievement_repo.list_all(limit=100)
        ]

    def get_child_achievements(self, child_id: int) -> list[ChildAchievementResponse]:
        cas = self.child_achievement_repo.get_by_child(child_id)
        results = []
        for ca in cas:
            resp = ChildAchievementResponse.model_validate(ca)
            if ca.achievement:
                resp.achievement_name = ca.achievement.name
                resp.achievement_emoji = ca.achievement.badge_emoji
            results.append(resp)
        return results

    def grant_achievement(self, child_id: int, achievement_id: int, context_data=None):
        """授予成就（幂等操作）"""
        if self.child_achievement_repo.has_achievement(child_id, achievement_id):
            return {"already_granted": True}

        ca = ChildAchievement(
            child_id=child_id,
            achievement_id=achievement_id,
            achieved_at=datetime.now(),
            context_data=context_data,
        )
        created = self.child_achievement_repo.create(ca)
        self.db.commit()
        return {"id": created.id, "already_granted": False}

    # ==================== 事件处理器辅助方法 ====================

    def increment_quizzes_passed(self, child_id: int) -> None:
        """增加当前级别的测验通过数"""
        current = self.child_level_repo.get_current(child_id)
        if current:
            current.quizzes_passed_at_level = (current.quizzes_passed_at_level or 0) + 1
            self.child_level_repo.update(current)

    def increment_books_read(self, child_id: int) -> None:
        """增加当前级别的读完书数"""
        current = self.child_level_repo.get_current(child_id)
        if current:
            current.books_read_at_level = (current.books_read_at_level or 0) + 1
            self.child_level_repo.update(current)

    # ==================== Quiz 查询（供 router 使用） ====================

    def get_quiz(self, quiz_id: int):
        """获取测验详情"""
        quiz = self.quiz_repo.get_by_id_or_raise(quiz_id)
        return quiz

    def list_quizzes(
        self, page: int = 1, page_size: int = 20, child_ids: list[int] | None = None
    ) -> dict:
        """获取测验记录列表（含孩子、图书、答题结果）"""
        from backend.domain.advancement.models import Quiz
        from backend.domain.child.models import Child
        from backend.domain.book.models import Book

        query = self.db.query(Quiz).filter(Quiz.is_deleted == 0)
        if child_ids is not None:
            if not child_ids:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_next": False,
                }
            query = query.filter(Quiz.child_id.in_(child_ids))
        total = query.count()
        quizzes = (
            query.order_by(Quiz.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        child_ids = list({q.child_id for q in quizzes if q.child_id})
        book_ids = list({q.book_id for q in quizzes if q.book_id})
        children = {}
        books = {}
        if child_ids:
            for c in (
                self.db.query(Child)
                .filter(Child.id.in_(child_ids), Child.is_deleted == 0)
                .all()
            ):
                children[c.id] = c.name
        if book_ids:
            for b in (
                self.db.query(Book)
                .filter(Book.id.in_(book_ids), Book.is_deleted == 0)
                .all()
            ):
                books[b.id] = {
                    "title": b.title,
                    "ar_value": float(b.ar_value) if b.ar_value is not None else None,
                }

        items = []
        for q in quizzes:
            book_info = books.get(q.book_id, {})
            score = float(q.score) if q.score is not None else None
            status_text = (
                "已完成"
                if q.status == Quiz.STATUS_COMPLETED
                else ("已过期" if q.status == Quiz.STATUS_EXPIRED else "进行中")
            )
            passed = None
            if score is not None:
                from backend.common.config_service import ConfigService
                from backend.common.types import PASS_THRESHOLD

                pass_rate = ConfigService.get_decimal(
                    self.db, "quiz_pass_rate", PASS_THRESHOLD
                )
                passed = score >= pass_rate * 100
            items.append(
                {
                    "id": q.id,
                    "child_id": q.child_id,
                    "child_name": children.get(q.child_id),
                    "book_id": q.book_id,
                    "book_title": book_info.get("title"),
                    "ar_value": book_info.get("ar_value"),
                    "status": q.status,
                    "status_text": status_text,
                    "total_questions": q.total_questions,
                    "correct_count": q.correct_count,
                    "score": score,
                    "passed": passed,
                    "create_time": q.create_time.isoformat() if q.create_time else None,
                }
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    # ==================== 级别 CRUD ====================

    def create_level(self, data) -> dict:
        """创建级别"""
        from backend.domain.advancement.models import Level

        dump = data.model_dump()
        if "pass_rate" in dump:
            dump["required_quiz_pass_rate"] = dump.pop("pass_rate")
        level = Level(**dump)
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return LevelResponse.model_validate(level)

    def update_level(self, level_id: int, data) -> dict:
        """更新级别"""
        from backend.domain.advancement.models import Level
        from backend.common.exceptions import NotFoundError

        level = (
            self.db.query(Level)
            .filter(Level.id == level_id, Level.is_deleted == 0)
            .first()
        )
        if not level:
            raise NotFoundError("级别不存在")
        update_data = data.model_dump(exclude_unset=True)
        if "pass_rate" in update_data:
            update_data["required_quiz_pass_rate"] = update_data.pop("pass_rate")
        for key, value in update_data.items():
            if hasattr(level, key):
                setattr(level, key, value)
        self.db.commit()
        return {"success": True, "message": "级别更新成功"}

    def delete_level(self, level_id: int) -> dict:
        """删除级别"""
        from backend.domain.advancement.models import Level
        from backend.common.exceptions import NotFoundError

        level = (
            self.db.query(Level)
            .filter(Level.id == level_id, Level.is_deleted == 0)
            .first()
        )
        if not level:
            raise NotFoundError("级别不存在")
        level.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "级别已删除"}

    # ==================== 成就 CRUD ====================

    def create_achievement(self, data) -> dict:
        """创建成就"""
        from backend.domain.advancement.models import Achievement

        achievement = Achievement(**data.model_dump())
        self.db.add(achievement)
        self.db.commit()
        self.db.refresh(achievement)
        return AchievementResponse.model_validate(achievement)

    def update_achievement(self, achievement_id: int, data) -> dict:
        """更新成就"""
        from backend.domain.advancement.models import Achievement
        from backend.common.exceptions import NotFoundError

        achievement = (
            self.db.query(Achievement)
            .filter(Achievement.id == achievement_id, Achievement.is_deleted == 0)
            .first()
        )
        if not achievement:
            raise NotFoundError("成就不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(achievement, key):
                setattr(achievement, key, value)
        self.db.commit()
        return {"success": True, "message": "成就更新成功"}

    def delete_achievement(self, achievement_id: int) -> dict:
        """删除成就"""
        from backend.domain.advancement.models import Achievement
        from backend.common.exceptions import NotFoundError

        achievement = (
            self.db.query(Achievement)
            .filter(Achievement.id == achievement_id, Achievement.is_deleted == 0)
            .first()
        )
        if not achievement:
            raise NotFoundError("成就不存在")
        achievement.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "成就已删除"}

    # ==================== 题库 CRUD ====================

    def create_question(self, data) -> dict:
        """创建题目"""
        from backend.domain.advancement.models import QuestionBank

        question = QuestionBank(**data.model_dump())
        self.db.add(question)
        self.db.commit()
        self.db.refresh(question)
        return QuestionResponse.model_validate(question)

    def update_question(self, question_id: int, data) -> dict:
        """更新题目"""
        from backend.domain.advancement.models import QuestionBank
        from backend.common.exceptions import NotFoundError

        question = (
            self.db.query(QuestionBank).filter(QuestionBank.id == question_id).first()
        )
        if not question:
            raise NotFoundError("题目不存在")
        update_data = data.model_dump(exclude_unset=True)
        allowed_fields = [
            "question_text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_answer",
            "difficulty",
            "explanation",
        ]
        for key, value in update_data.items():
            if key in allowed_fields:
                setattr(question, key, value)
        self.db.commit()
        return QuestionResponse.model_validate(question)

    def delete_question(self, question_id: int) -> dict:
        """删除题目"""
        from backend.domain.advancement.models import QuestionBank
        from backend.common.exceptions import NotFoundError

        question = (
            self.db.query(QuestionBank).filter(QuestionBank.id == question_id).first()
        )
        if not question:
            raise NotFoundError("题目不存在")
        question.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "题目已删除"}

    def review_submission(self, submission_id: int, data) -> dict:
        """审核提交"""
        from backend.domain.advancement.models import ReadingSubmission
        from backend.common.exceptions import NotFoundError

        sub = (
            self.db.query(ReadingSubmission)
            .filter(ReadingSubmission.id == submission_id)
            .first()
        )
        if not sub:
            raise NotFoundError("提交不存在")
        sub.status = data.status
        if data.comment:
            sub.teacher_comment = data.comment

        # P0-9: 审核通过 → 增加已读书数 + 触发晋级检测
        if data.status == ReadingSubmission.STATUS_APPROVED:
            sub.reviewed_at = datetime.now()
            self.increment_books_read(sub.child_id)
            self.check_and_advance(sub.child_id)

        self.db.commit()
        return {"success": True}

    # ==================== 管理端查询方法 ====================

    def list_achievement_records(self, page: int = 1, page_size: int = 20) -> dict:
        """获取成就记录列表 — 带分页"""
        from backend.domain.advancement.models import ChildAchievement
        from backend.domain.child.models import Child

        total = (
            self.db.query(ChildAchievement)
            .filter(ChildAchievement.is_deleted == 0)
            .count()
        )

        records = (
            self.db.query(ChildAchievement)
            .filter(ChildAchievement.is_deleted == 0)
            .order_by(ChildAchievement.achieved_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量查询所有相关 child 和 achievement，避免 N+1
        child_ids = list(set(r.child_id for r in records if r.child_id))
        children = {}
        if child_ids:
            for c in (
                self.db.query(Child)
                .filter(Child.id.in_(child_ids), Child.is_deleted == 0)
                .all()
            ):
                children[c.id] = c.name

        from backend.domain.advancement.models import Achievement

        ach_ids = list(set(r.achievement_id for r in records if r.achievement_id))
        achievements = {}
        if ach_ids:
            for a in (
                self.db.query(Achievement).filter(Achievement.id.in_(ach_ids)).all()
            ):
                achievements[a.id] = {
                    "name": a.name,
                    "type": a.type,
                    "badge_emoji": a.badge_emoji,
                    "trigger_condition": a.trigger_condition,
                }

        result = []
        for r in records:
            ach = achievements.get(r.achievement_id, {})
            result.append(
                {
                    "id": r.id,
                    "child_id": r.child_id,
                    "child_name": children.get(r.child_id),
                    "achievement_id": r.achievement_id,
                    "achievement_name": ach.get("name"),
                    "achievement_type": ach.get("type"),
                    "badge_emoji": ach.get("badge_emoji"),
                    "trigger_condition": ach.get("trigger_condition"),
                    "achieved_at": r.achieved_at.isoformat()
                    if hasattr(r, "achieved_at") and r.achieved_at
                    else None,
                }
            )

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def list_certificates(self, page: int = 1, page_size: int = 20) -> dict:
        """获取证书列表 — 关联孩子累计阅读数据"""
        from backend.domain.certificate.models import LevelCertificate
        from backend.domain.child.models import Child
        from datetime import datetime

        query = (
            self.db.query(LevelCertificate, Child)
            .outerjoin(Child, LevelCertificate.child_id == Child.id)
            .filter(LevelCertificate.is_deleted == 0)
        )
        total = query.count()
        rows = (
            query.order_by(LevelCertificate.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = [
            {
                "id": c.id,
                "child_id": c.child_id,
                "child_name": c.child_name,
                "level_name": c.level_name,
                "certificate_no": c.certificate_no,
                "issued_at": c.issued_at.isoformat() if c.issued_at else None,
                "create_time": c.create_time.isoformat() if c.create_time else None,
                "book_count": child.total_books_finished or 0 if child else 0,
                "word_count": child.total_words_read or 0 if child else 0,
            }
            for c, child in rows
        ]

        # 统计信息
        current_month = datetime.now().strftime("%Y-%m")
        last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime(
            "%Y-%m"
        )
        month_new = sum(
            1
            for c, _ in rows
            if (c.issued_at and c.issued_at.strftime("%Y-%m") == current_month)
            or (
                not c.issued_at
                and c.create_time
                and c.create_time.strftime("%Y-%m") == current_month
            )
        )
        last_month_new = sum(
            1
            for c, _ in rows
            if (c.issued_at and c.issued_at.strftime("%Y-%m") == last_month)
            or (
                not c.issued_at
                and c.create_time
                and c.create_time.strftime("%Y-%m") == last_month
            )
        )
        levels = sorted(
            {c.level_name for c, _ in rows if c.level_name},
            key=lambda x: (len(x), x),
        )

        return {
            "items": items,
            "stats": {
                "total": total,
                "month_new": month_new,
                "month_change": month_new - last_month_new,
                "level_count": len(levels),
                "level_min": levels[0] if levels else None,
                "level_max": levels[-1] if levels else None,
                "pending_regen": 0,
            },
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def get_certificate(self, cert_id: int) -> dict:
        """获取证书详情 — 关联孩子累计阅读数据"""
        from backend.domain.certificate.models import LevelCertificate
        from backend.domain.child.models import Child
        from backend.common.exceptions import NotFoundError

        row = (
            self.db.query(LevelCertificate, Child)
            .outerjoin(Child, LevelCertificate.child_id == Child.id)
            .filter(
                LevelCertificate.id == cert_id,
                LevelCertificate.is_deleted == 0,
            )
            .first()
        )
        if not row:
            raise NotFoundError("证书不存在")
        cert, child = row

        return {
            "id": cert.id,
            "child_id": cert.child_id,
            "child_name": cert.child_name,
            "level_name": cert.level_name,
            "certificate_no": cert.certificate_no,
            "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
            "create_time": cert.create_time.isoformat() if cert.create_time else None,
            "book_count": child.total_books_finished or 0 if child else 0,
            "word_count": child.total_words_read or 0 if child else 0,
        }

    def update_certificate(self, cert_id: int, data) -> dict:
        """更新证书"""
        from backend.domain.certificate.models import LevelCertificate
        from backend.common.exceptions import NotFoundError

        cert = (
            self.db.query(LevelCertificate)
            .filter(LevelCertificate.id == cert_id, LevelCertificate.is_deleted == 0)
            .first()
        )
        if not cert:
            raise NotFoundError("证书不存在")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(cert, key):
                setattr(cert, key, value)
        self.db.commit()
        return {"success": True, "message": "证书更新成功"}

    def list_submissions(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str = None,
        child_ids: list[int] | None = None,
    ) -> dict:
        """获取提交记录列表 — 支持逗号分隔多状态"""
        from backend.domain.advancement.models import ReadingSubmission
        from backend.domain.child.models import Child
        from backend.domain.book.models import Book

        query = self.db.query(ReadingSubmission).filter(
            ReadingSubmission.is_deleted == 0
        )
        if child_ids is not None:
            if not child_ids:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_next": False,
                }
            query = query.filter(ReadingSubmission.child_id.in_(child_ids))
        if status:
            status_list = [
                int(s.strip()) for s in status.split(",") if s.strip().isdigit()
            ]
            if status_list:
                query = query.filter(ReadingSubmission.status.in_(status_list))

        total = query.count()
        subs = (
            query.order_by(ReadingSubmission.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量查询 child 和 book，避免 N+1
        child_ids = list(set(s.child_id for s in subs if s.child_id))
        book_ids = list(set(s.book_id for s in subs if s.book_id))
        children = {}
        books = {}
        if child_ids:
            for c in (
                self.db.query(Child)
                .filter(Child.id.in_(child_ids), Child.is_deleted == 0)
                .all()
            ):
                children[c.id] = {
                    "name": c.name,
                    "ar_level": getattr(c, "ar_level", None),
                }
        if book_ids:
            for b in (
                self.db.query(Book)
                .filter(Book.id.in_(book_ids), Book.is_deleted == 0)
                .all()
            ):
                books[b.id] = {
                    "title": b.title,
                    "total_pages": getattr(b, "total_pages", None),
                }

        result = []
        for s in subs:
            child_info = children.get(s.child_id, {})
            book_info = books.get(s.book_id, {})
            result.append(
                {
                    "id": s.id,
                    "child_id": s.child_id,
                    "child_name": child_info.get("name"),
                    "book_id": s.book_id,
                    "book_title": book_info.get("title"),
                    "status": s.status,
                    "submitted_at": s.submitted_at.isoformat()
                    if getattr(s, "submitted_at", None)
                    else (s.create_time.isoformat() if s.create_time else None),
                    "create_time": s.create_time.isoformat() if s.create_time else None,
                    "level": child_info.get("ar_level"),
                    "total_pages": book_info.get("total_pages"),
                }
            )

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def list_questions(
        self, page: int = 1, page_size: int = 20, keyword: str = None
    ) -> dict:
        """获取题库列表"""
        from backend.domain.advancement.models import QuestionBank

        query = self.db.query(QuestionBank).filter(QuestionBank.is_deleted == 0)
        if keyword:
            query = query.filter(QuestionBank.question_text.ilike(f"%{keyword}%"))

        total = query.count()
        items = (
            query.order_by(QuestionBank.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "items": [
                {
                    "id": q.id,
                    "question_text": q.question_text,
                    "option_a": q.option_a,
                    "option_b": q.option_b,
                    "option_c": q.option_c,
                    "option_d": q.option_d,
                    "correct_answer": q.correct_answer,
                    "difficulty": q.difficulty,
                    "explanation": q.explanation,
                    "create_time": q.create_time.isoformat() if q.create_time else None,
                }
                for q in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def regenerate_certificate(self, cert_id: int) -> dict:
        """重新生成证书 — 更新编号、颁发时间及冗余信息"""
        from backend.domain.certificate.models import LevelCertificate
        from backend.domain.child.models import Child
        from backend.domain.advancement.models import Level
        from backend.common.exceptions import NotFoundError
        from datetime import datetime
        import uuid

        cert = (
            self.db.query(LevelCertificate)
            .filter(LevelCertificate.id == cert_id, LevelCertificate.is_deleted == 0)
            .first()
        )
        if not cert:
            raise NotFoundError("证书不存在")

        child = (
            self.db.query(Child)
            .filter(Child.id == cert.child_id, Child.is_deleted == 0)
            .first()
        )
        level = (
            self.db.query(Level)
            .filter(Level.id == cert.level_id, Level.is_deleted == 0)
            .first()
        )

        cert.certificate_no = (
            f"MW-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        )
        cert.issued_at = datetime.now()
        if child:
            cert.child_name = child.name
            cert.child_english_name = child.english_name
        if level:
            cert.level_name = level.name
            cert.badge_emoji = level.badge_emoji

        self.db.commit()
        return {
            "success": True,
            "message": "证书已重新生成",
            "certificate_no": cert.certificate_no,
            "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
        }

    def delete_certificate(self, cert_id: int) -> dict:
        """删除证书"""
        from backend.domain.certificate.models import LevelCertificate
        from backend.common.exceptions import NotFoundError

        cert = (
            self.db.query(LevelCertificate)
            .filter(LevelCertificate.id == cert_id, LevelCertificate.is_deleted == 0)
            .first()
        )
        if not cert:
            raise NotFoundError("证书不存在")
        cert.soft_delete()
        self.db.commit()
        return {"success": True, "message": "证书已删除"}
