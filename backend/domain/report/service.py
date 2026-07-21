# backend/domain/report/service.py
"""报告域业务逻辑 — 观察期报告/学习报告/阅读统计

聚合其他域数据，生成报告和统计数据。
跨域数据通过模型直接引用（报告域是只读聚合域）。
"""

import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.exceptions import NotFoundError
from backend.common.types import MemberStatus, PASS_THRESHOLD
from backend.common.config_service import ConfigService
from backend.domain.advancement.models import ChildLevel, Level, Quiz, ReadingSubmission
from backend.domain.child.models import Child
from backend.domain.reading.models import CheckIn, ReadingProgress, ReadingSession
from backend.domain.report.models import ObservationReport
from backend.domain.report.repository import (
    ObservationReportRepository,
    LearningReportRepository,
)
from backend.domain.report.schemas import (
    LearningReportResponse,
    ObservationReportDetailResponse,
    MarkViewedResponse,
    SummaryResponse,
    TodayStatsResponse,
    TrendEntryResponse,
    WeeklyReportResponse,
)
from backend.domain.voice.models import VoiceRecording
from backend.domain.vocabulary.models import UserVocabulary

logger = logging.getLogger(__name__)

OBSERVATION_DAYS = 30  # 默认值，可通过 SystemConfig observation_days 配置


class ReportService:
    """报告服务

    架构意图：
      - 观察期报告/学习报告的 CRUD
      - 阅读统计数据的聚合查询（跨域只读）
      - 统计数据通过跨域模型直接查询，不做写操作
    """

    def __init__(self, db: Session):
        self.db = db
        self.observation_repo = ObservationReportRepository(db)
        self.learning_repo = LearningReportRepository(db)
        self.child_repo = BaseRepository(db, Child)

    # ==================== 学习报告 ====================

    def get_observation_report(self, child_id: int) -> dict | None:
        reports = self.observation_repo.list_all(limit=1, child_id=child_id)
        if not reports:
            return None
        r = reports[0]
        return {
            "id": r.id,
            "child_id": r.child_id,
            "total_books_read": r.total_books_read,
            "total_words_read": r.total_words_read,
            "total_reading_minutes": r.total_reading_minutes,
            "quizzes_attempted": r.quizzes_attempted,
            "quizzes_passed": r.quizzes_passed,
            "current_level": r.level_at_end,
            "teacher_comment": r.teacher_comment,
            "teacher_id": getattr(r, "teacher_id", None),
            "status": r.status,
            "observation_start": r.start_date.isoformat() if r.start_date else None,
            "observation_end": r.end_date.isoformat() if r.end_date else None,
            "generated_at": r.create_time.isoformat() if r.create_time else None,
        }

    def get_learning_report(self, child_id: int) -> LearningReportResponse | None:
        reports = self.learning_repo.list_all(limit=1, child_id=child_id)
        if not reports:
            return None
        return LearningReportResponse.model_validate(reports[0])

    # ==================== 观察期报告（完整功能） ====================

    def get_observation_report_detail(self, child_id: int) -> dict | None:
        """获取孩子的观察期报告详情"""
        report = (
            self.db.query(ObservationReport)
            .filter(
                ObservationReport.child_id == child_id,
            )
            .order_by(ObservationReport.id.desc())
            .first()
        )
        if not report:
            return None
        return ObservationReportDetailResponse(
            id=report.id,
            child_id=report.child_id,
            total_books_read=report.total_books_read,
            total_words_read=report.total_words_read,
            total_reading_minutes=report.total_reading_minutes,
            quizzes_attempted=getattr(report, "quizzes_attempted", 0),
            quizzes_passed=getattr(report, "quizzes_passed", 0),
            current_level=getattr(report, "level_at_end", None)
            or getattr(report, "current_level", None),
            teacher_comment=report.teacher_comment,
            teacher_id=getattr(report, "teacher_id", None),
            status=report.status,
            observation_start=report.start_date,
            observation_end=report.end_date,
            generated_at=report.create_time,
        )

    def generate_due_reports(self) -> list:
        """为所有到期的观察期孩子生成报告（返回 list[dict]，向后兼容）"""
        # 从配置读取观察期天数
        from backend.common.config_service import ConfigService

        obs_days = ConfigService.get_int(self.db, "observation_days", OBSERVATION_DAYS)
        cutoff = datetime.now() - timedelta(days=obs_days)
        children = (
            self.db.query(Child)
            .filter(
                Child.status == MemberStatus.OBSERVATION,
                Child.member_start_time <= cutoff,
                Child.is_deleted == 0,
            )
            .all()
        )

        child_ids = [c.id for c in children]
        existing_report_ids = {
            r.child_id
            for r in self.db.query(ObservationReport.child_id)
            .filter(ObservationReport.child_id.in_(child_ids))
            .all()
        }

        generated = []
        for child in children:
            if child.id in existing_report_ids:
                continue

            report = self._generate_for_child(child)
            if report:
                generated.append({"child_id": child.id, "report_id": report.id})

        logger.info(f"Generated {len(generated)} observation reports")
        return generated

    def _generate_for_child(self, child: Child) -> ObservationReport | None:
        """为单个孩子生成观察期报告"""
        obs_start = child.member_start_time or child.create_time
        obs_end = datetime.now()

        # 统计阅读提交
        submissions = (
            self.db.query(ReadingSubmission)
            .filter(
                ReadingSubmission.child_id == child.id,
                ReadingSubmission.status == ReadingSubmission.STATUS_APPROVED,
                ReadingSubmission.submitted_at >= obs_start,
                ReadingSubmission.submitted_at <= obs_end,
            )
            .all()
        )
        total_books = len(submissions)
        total_words = sum(s.word_count or 0 for s in submissions)

        # 统计测验
        quizzes = (
            self.db.query(Quiz)
            .filter(
                Quiz.child_id == child.id,
                Quiz.create_time >= obs_start,
                Quiz.create_time <= obs_end,
            )
            .all()
        )
        quizzes_attempted = len(quizzes)
        pass_rate = ConfigService.get_decimal(self.db, "quiz_pass_rate", PASS_THRESHOLD)
        quizzes_passed = sum(
            1
            for q in quizzes
            if q.status == Quiz.STATUS_COMPLETED
            and q.score
            and q.score >= pass_rate * 100
        )

        # 统计阅读时长
        sessions = (
            self.db.query(ReadingSession)
            .filter(
                ReadingSession.child_id == child.id,
                ReadingSession.start_time >= obs_start,
            )
            .all()
        )
        total_minutes = sum(
            ((s.end_time or s.start_time) - s.start_time).total_seconds() / 60
            for s in sessions
            if s.start_time
        )

        # 当前级别
        current_cl = (
            self.db.query(ChildLevel)
            .filter(
                ChildLevel.child_id == child.id,
                ChildLevel.is_current,
            )
            .first()
        )
        level_name = None
        if current_cl:
            level = self.db.query(Level).filter(Level.id == current_cl.level_id).first()
            level_name = level.name if level else None

        report = ObservationReport(
            child_id=child.id,
            start_date=obs_start,
            end_date=obs_end,
            total_books_read=total_books,
            total_words_read=total_words,
            total_reading_minutes=int(total_minutes),
            level_at_end=level_name,
            quizzes_attempted=quizzes_attempted,
            quizzes_passed=quizzes_passed,
            status=1,
        )
        self.observation_repo.create(report)
        self.db.commit()
        logger.info(
            f"Observation report generated: child={child.id}, books={total_books}, words={total_words}"
        )
        return report

    def mark_observation_viewed(self, report_id: int) -> dict:
        """标记报告已查看"""
        report = self.observation_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError("报告不存在")
        report.status = 2  # STATUS_VIEWED
        self.observation_repo.update(report)
        self.db.commit()
        return MarkViewedResponse(success=True)

    # 向后兼容别名
    def mark_viewed(self, report_id: int) -> dict:
        return self.mark_observation_viewed(report_id)

    def add_teacher_comment(
        self, report_id: int, teacher_id: int, comment: str
    ) -> dict:
        """老师添加评语"""
        report = self.observation_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError("报告不存在")
        report.teacher_comment = comment
        if hasattr(report, "teacher_id"):
            report.teacher_id = teacher_id
        self.observation_repo.update(report)
        self.db.commit()
        return {"success": True, "teacher_comment": comment, "teacher_id": teacher_id}

    def render_report_html(self, child_id: int) -> str | None:
        """渲染观察期报告为HTML（Jinja2模板）"""
        report = (
            self.db.query(ObservationReport)
            .filter(ObservationReport.child_id == child_id)
            .order_by(ObservationReport.id.desc())
            .first()
        )
        if not report:
            return None

        child = self.child_repo.get_by_id(child_id)
        level_name = getattr(report, "level_at_end", None) or "未分级"

        # 查询级别对应的 badge_emoji
        badge_emoji = ""
        if level_name != "未分级":
            from backend.domain.advancement.models import Level

            level = (
                self.db.query(Level)
                .filter(Level.name == level_name, Level.is_deleted == 0)
                .first()
            )
            if level and level.badge_emoji:
                badge_emoji = level.badge_emoji

        pass_rate = 0
        quizzes_attempted = getattr(report, "quizzes_attempted", 0)
        quizzes_passed = getattr(report, "quizzes_passed", 0)
        if quizzes_attempted and quizzes_attempted > 0:
            pass_rate = round(quizzes_passed / quizzes_attempted * 100)

        teacher_comment = ""
        if report.teacher_comment:
            teacher_comment = report.teacher_comment

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "templates",
            "observation_report.html",
        )
        try:
            from jinja2 import Environment, select_autoescape

            env = Environment(
                autoescape=select_autoescape(default=True, default_for_string=True)
            )
            with open(template_path, encoding="utf-8") as f:
                template = env.from_string(f.read())
        except FileNotFoundError:
            logger.warning(f"Template not found: {template_path}")
            return None

        return template.render(
            child_name=child.name if child else "",
            english_name=child.english_name if child else "",
            obs_start=report.start_date.strftime("%Y-%m-%d")
            if report.start_date
            else "",
            obs_end=report.end_date.strftime("%Y-%m-%d") if report.end_date else "",
            badge_emoji=badge_emoji,
            level_name=level_name,
            total_books=report.total_books_read,
            total_words=f"{report.total_words_read:,}",
            total_minutes=report.total_reading_minutes,
            quizzes_attempted=quizzes_attempted,
            quizzes_passed=quizzes_passed,
            pass_rate=pass_rate,
            teacher_comment_section=teacher_comment,
            generated_at=report.create_time.strftime("%Y-%m-%d %H:%M")
            if report.create_time
            else "",
        )

    async def render_report_pdf(self, child_id: int) -> bytes | None:
        """渲染观察期报告为PDF（异步线程，避免阻塞事件循环）"""
        import asyncio
        from backend.common.pdf_service import PDFService

        html = self.render_report_html(child_id)
        if not html:
            return None

        svc = PDFService()
        return await asyncio.to_thread(svc.render_pdf, html)

    # ==================== 阅读统计 ====================

    def get_summary(self, child_id: int) -> dict:
        """累计统计"""
        total_minutes = (
            self.db.query(func.sum(ReadingSession.duration_seconds))
            .filter(
                ReadingSession.child_id == child_id,
            )
            .scalar()
            or 0
        )
        total_words = (
            self.db.query(func.sum(ReadingSession.words_read))
            .filter(
                ReadingSession.child_id == child_id,
            )
            .scalar()
            or 0
        )
        books_finished = (
            self.db.query(ReadingProgress)
            .filter(
                ReadingProgress.child_id == child_id,
                ReadingProgress.is_finished == 1,
            )
            .count()
        )
        vocab_count = (
            self.db.query(UserVocabulary)
            .filter(
                UserVocabulary.child_id == child_id,
            )
            .count()
        )
        voice_count = (
            self.db.query(VoiceRecording)
            .filter(
                VoiceRecording.child_id == child_id,
                VoiceRecording.is_deleted == 0,
            )
            .count()
        )

        child = self.child_repo.get_by_id(child_id)
        return SummaryResponse(
            total_reading_minutes=total_minutes // 60,
            total_words_read=total_words,
            books_finished=books_finished,
            vocabulary_count=vocab_count,
            voice_practices=voice_count,
            current_streak=child.current_streak_days if child else 0,
            longest_streak=child.longest_streak_days if child else 0,
        )

    def get_today_stats(self, child_id: int) -> dict:
        """今日统计"""
        today = date.today()
        today_sessions = (
            self.db.query(
                func.sum(ReadingSession.duration_seconds),
                func.sum(ReadingSession.words_read),
                func.sum(ReadingSession.pages_read),
            )
            .filter(
                ReadingSession.child_id == child_id,
                func.date(ReadingSession.start_time) == today,
            )
            .first()
        )

        return TodayStatsResponse(
            reading_minutes=(today_sessions[0] or 0) // 60,
            words_read=today_sessions[1] or 0,
            pages_read=today_sessions[2] or 0,
        )

    def get_trend(self, child_id: int, days: int = 7) -> list[TrendEntryResponse]:
        """阅读趋势（最近N天）— 单次 GROUP BY 查询"""
        since = date.today() - timedelta(days=days - 1)
        rows = (
            self.db.query(
                func.date(ReadingSession.start_time).label("day"),
                func.sum(ReadingSession.duration_seconds),
                func.sum(ReadingSession.words_read),
            )
            .filter(
                ReadingSession.child_id == child_id,
                ReadingSession.start_time >= since,
            )
            .group_by(func.date(ReadingSession.start_time))
            .all()
        )
        stats_by_day = {r[0]: r for r in rows}
        result = []
        for i in range(days - 1, -1, -1):
            d = date.today() - timedelta(days=i)
            ds = d.isoformat()
            stats = stats_by_day.get(ds)
            result.append(
                TrendEntryResponse(
                    date=ds,
                    reading_minutes=(stats[1] or 0) // 60 if stats else 0,
                    words_read=stats[2] or 0 if stats else 0,
                )
            )
        return result

    def generate_weekly_report(self, child_id: int) -> dict:
        """生成周报"""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        week_stats = (
            self.db.query(
                func.sum(ReadingSession.duration_seconds),
                func.sum(ReadingSession.words_read),
            )
            .filter(
                ReadingSession.child_id == child_id,
                func.date(ReadingSession.start_time) >= week_start,
                func.date(ReadingSession.start_time) <= week_end,
            )
            .first()
        )

        books_this_week = (
            self.db.query(ReadingProgress)
            .filter(
                ReadingProgress.child_id == child_id,
                ReadingProgress.is_finished == 1,
                func.date(ReadingProgress.finish_time) >= week_start,
                func.date(ReadingProgress.finish_time) <= week_end,
            )
            .count()
        )

        new_vocab = (
            self.db.query(UserVocabulary)
            .filter(
                UserVocabulary.child_id == child_id,
                func.date(UserVocabulary.create_time) >= week_start,
                func.date(UserVocabulary.create_time) <= week_end,
            )
            .count()
        )

        checkin_days = (
            self.db.query(CheckIn)
            .filter(
                CheckIn.child_id == child_id,
                CheckIn.check_date >= week_start,
                CheckIn.check_date <= week_end,
            )
            .count()
        )

        child = self.child_repo.get_by_id(child_id)

        return WeeklyReportResponse(
            report_type="weekly",
            period=f"{week_start.isoformat()} ~ {week_end.isoformat()}",
            total_minutes=(week_stats[0] or 0) // 60,
            total_words=week_stats[1] or 0,
            books_finished=books_this_week,
            new_vocabulary=new_vocab,
            voice_practices=(
                self.db.query(VoiceRecording)
                .filter(
                    VoiceRecording.child_id == child_id,
                    VoiceRecording.is_deleted == 0,
                    func.date(VoiceRecording.create_time) >= week_start,
                    func.date(VoiceRecording.create_time) <= week_end,
                )
                .count()
            ),
            checkin_days=checkin_days,
            current_ar_level=float(child.ar_level)
            if child and child.ar_level
            else None,
            streak_days=child.current_streak_days if child else 0,
            suggestion=self._generate_suggestion(child),
        )

    def generate_monthly_report(self, child_id: int) -> dict:
        """生成月报"""
        today = date.today()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(
                days=1
            )
        else:
            month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        month_stats = (
            self.db.query(
                func.sum(ReadingSession.duration_seconds),
                func.sum(ReadingSession.words_read),
            )
            .filter(
                ReadingSession.child_id == child_id,
                func.date(ReadingSession.start_time) >= month_start,
                func.date(ReadingSession.start_time) <= month_end,
            )
            .first()
        )

        books_this_month = (
            self.db.query(ReadingProgress)
            .filter(
                ReadingProgress.child_id == child_id,
                ReadingProgress.is_finished == 1,
                func.date(ReadingProgress.finish_time) >= month_start,
                func.date(ReadingProgress.finish_time) <= month_end,
            )
            .count()
        )

        checkin_days = (
            self.db.query(CheckIn)
            .filter(
                CheckIn.child_id == child_id,
                CheckIn.check_date >= month_start,
                CheckIn.check_date <= month_end,
            )
            .count()
        )

        child = self.child_repo.get_by_id(child_id)
        total_days = (month_end - month_start).days + 1
        checkin_rate = round(checkin_days / total_days * 100) if total_days > 0 else 0

        return {
            "report_type": "monthly",
            "period": f"{month_start.isoformat()} ~ {month_end.isoformat()}",
            "total_minutes": (month_stats[0] or 0) // 60,
            "total_words": month_stats[1] or 0,
            "books_finished": books_this_month,
            "checkin_days": checkin_days,
            "checkin_rate": checkin_rate,
            "current_ar_level": float(child.ar_level)
            if child and child.ar_level
            else None,
            "streak_days": child.current_streak_days if child else 0,
        }

    @staticmethod
    def _generate_suggestion(child: Optional[Child]) -> str:
        """生成阅读建议"""
        if not child:
            return "开始你的阅读之旅吧！"
        if child.current_streak_days >= 21:
            return "已连续阅读21天，太棒了！建议尝试更高AR等级的图书。"
        if child.current_streak_days >= 7:
            return "坚持得不错！继续保持每日阅读习惯。"
        if child.total_reading_minutes < 100:
            return "建议每天阅读至少10分钟，养成英文阅读习惯。"
        return "继续加油，每天进步一点点！"

    @staticmethod
    def _to_dict(report):
        """Convert ObservationReport to dict for backward compatibility"""
        if not report:
            return None
        return {
            "id": report.id,
            "child_id": report.child_id,
            "total_books_read": report.total_books_read,
            "total_words_read": report.total_words_read,
            "total_reading_minutes": report.total_reading_minutes,
            "quizzes_attempted": report.quizzes_attempted,
            "quizzes_passed": report.quizzes_passed,
            "current_level": report.level_at_end,
            "teacher_comment": report.teacher_comment,
            "teacher_id": report.teacher_id,
            "status": report.status,
            "observation_start": report.start_date.isoformat()
            if report.start_date
            else None,
            "observation_end": report.end_date.isoformat() if report.end_date else None,
            "generated_at": report.create_time.isoformat()
            if report.create_time
            else None,
        }

    def get_report(self, child_id: int) -> dict | None:
        """向后兼容：get_report = get_observation_report"""
        return self.get_observation_report(child_id)

    def get_report_by_id(self, report_id: int) -> dict | None:
        report = self.observation_repo.get_by_id(report_id)
        if not report:
            return None
        return (
            self._to_dict(report)
            if hasattr(self, "_to_dict")
            else {
                "id": report.id,
                "child_id": report.child_id,
                "total_books_read": report.total_books_read,
                "total_words_read": report.total_words_read,
            }
        )
