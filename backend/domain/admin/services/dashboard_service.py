# backend/domain/admin/services/dashboard_service.py
"""管理端仪表盘 Service — 从 AdminService 拆分出来的独立域服务。"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.config_service import ConfigService
from backend.common.types import BorrowStatus, PASS_THRESHOLD
from backend.domain.admin.schemas import AdminDashboardResponse
from backend.domain.advancement.models import Quiz
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.reading.models import ReadingSession
from backend.domain.user.models import User


class AdminDashboardService:
    """管理仪表盘聚合查询。"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = BaseRepository(db, User)
        self.child_repo = BaseRepository(db, Child)
        self.order_repo = BaseRepository(db, Order)

    def get_dashboard(self) -> AdminDashboardResponse:
        """管理仪表盘"""
        today = date.today()
        week_ago = today - timedelta(days=7)

        total_users = self.user_repo.count()
        total_children = self.child_repo.count()
        total_orders = self.order_repo.count()
        total_revenue = (
            self.db.query(func.sum(Order.amount))
            .filter(Order.pay_status == 1, Order.is_deleted == 0)
            .scalar()
        )
        total_revenue = total_revenue if total_revenue is not None else Decimal("0")

        # 日活用户：今日有阅读会话的 child 数
        daily_active_users = (
            self.db.query(func.count(func.distinct(ReadingSession.child_id)))
            .filter(
                func.date(ReadingSession.start_time) == today,
                ReadingSession.is_deleted == 0,
            )
            .scalar()
            or 0
        )

        # 本周新增用户
        new_users_this_week = (
            self.db.query(func.count(User.id))
            .filter(
                User.create_time >= week_ago,
                User.is_deleted == 0,
            )
            .scalar()
            or 0
        )

        # 当前借阅量（借阅中）
        active_borrows = (
            self.db.query(func.count(BorrowRecord.id))
            .filter(
                BorrowRecord.status == BorrowStatus.BORROWING,
                BorrowRecord.is_deleted == 0,
            )
            .scalar()
            or 0
        )

        # 测评通过率 — 从配置读取通过率阈值
        pass_threshold = ConfigService.get_decimal(
            self.db, "quiz_pass_rate", PASS_THRESHOLD
        )
        pass_score = pass_threshold * 100  # 0.8 → 80
        total_quizzes = (
            self.db.query(func.count(Quiz.id))
            .filter(
                Quiz.status == Quiz.STATUS_COMPLETED,
                Quiz.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        passed_quizzes = (
            self.db.query(func.count(Quiz.id))
            .filter(
                Quiz.status == Quiz.STATUS_COMPLETED,
                Quiz.score >= pass_score,
                Quiz.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        quiz_pass_rate = (
            round(passed_quizzes / total_quizzes * 100, 1) if total_quizzes > 0 else 0.0
        )

        # 今日阅读总时长（分钟）
        today_reading_seconds = (
            self.db.query(func.sum(ReadingSession.duration_seconds))
            .filter(
                ReadingSession.is_deleted == 0,
                func.date(ReadingSession.start_time) == today,
            )
            .scalar()
            or 0
        )
        today_reading_minutes = int(today_reading_seconds) // 60

        # 今日新增生词（按加入生词本时间统计）
        from backend.domain.vocabulary.models import UserVocabulary

        today_new_words = (
            self.db.query(func.count(UserVocabulary.id))
            .filter(
                UserVocabulary.is_deleted == 0,
                func.date(UserVocabulary.create_time) == today,
            )
            .scalar()
            or 0
        )

        # 今日朗读次数
        from backend.domain.voice.models import VoiceRecording

        today_voice_count = (
            self.db.query(func.count(VoiceRecording.id))
            .filter(
                VoiceRecording.is_deleted == 0,
                func.date(VoiceRecording.create_time) == today,
            )
            .scalar()
            or 0
        )

        return AdminDashboardResponse(
            total_users=total_users,
            total_children=total_children,
            total_orders=total_orders,
            total_revenue=total_revenue,
            daily_active_users=daily_active_users,
            new_users_this_week=new_users_this_week,
            active_borrows=active_borrows,
            quiz_pass_rate=quiz_pass_rate,
            today_reading_minutes=today_reading_minutes,
            today_new_words=today_new_words,
            today_voice_count=today_voice_count,
        )
