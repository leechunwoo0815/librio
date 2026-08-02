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

    def get_ops_metrics(self) -> dict:
        """E6 运营核心报表（运营负责人每日/每周/每月必看）

        - 今日借还量、本周新增/流失会员、逾期率排行
        - 押金池总额/待退押金、转化漏斗（亲子课→观察期→正式）
        """
        from backend.domain.deposit.models import DepositRecord
        from backend.common.types import (
            DepositStatus,
            MemberStatus,
            OrderType,
            PayStatus,
        )

        today = date.today()
        week_ago = today - timedelta(days=7)

        # 今日借出/归还量
        today_borrows = (
            self.db.query(func.count(BorrowRecord.id))
            .filter(
                func.date(BorrowRecord.borrow_time) == today,
                BorrowRecord.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        today_returns = (
            self.db.query(func.count(BorrowRecord.id))
            .filter(
                func.date(BorrowRecord.return_time) == today,
                BorrowRecord.is_deleted == 0,
            )
            .scalar()
            or 0
        )

        # 本周新增会员（开始观察期/正式）/流失（转为已过期）
        week_new_members = (
            self.db.query(func.count(Child.id))
            .filter(
                Child.member_start_time >= week_ago,
                Child.status.in_([MemberStatus.OBSERVATION, MemberStatus.OFFICIAL]),
                Child.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        week_lost_members = (
            self.db.query(func.count(Child.id))
            .filter(
                Child.status == MemberStatus.EXPIRED,
                Child.update_time >= week_ago,
                Child.is_deleted == 0,
            )
            .scalar()
            or 0
        )

        # 逾期率排行（按孩子：未缴罚款 Top5；按书：逾期记录数 Top5）
        overdue_by_child = (
            self.db.query(
                Child.id,
                Child.name,
                func.count(BorrowRecord.id).label("overdue_count"),
                func.coalesce(func.sum(BorrowRecord.fine_amount), 0).label(
                    "fine_total"
                ),
            )
            .join(BorrowRecord, BorrowRecord.child_id == Child.id)
            .filter(
                BorrowRecord.status == BorrowStatus.OVERDUE,
                BorrowRecord.is_deleted == 0,
                Child.is_deleted == 0,
            )
            .group_by(Child.id, Child.name)
            .order_by(func.count(BorrowRecord.id).desc())
            .limit(5)
            .all()
        )
        from backend.domain.book.models import Book

        overdue_by_book = (
            self.db.query(
                Book.id,
                Book.title,
                func.count(BorrowRecord.id).label("overdue_count"),
            )
            .join(BorrowRecord, BorrowRecord.book_id == Book.id)
            .filter(
                BorrowRecord.status == BorrowStatus.OVERDUE,
                BorrowRecord.is_deleted == 0,
                Book.is_deleted == 0,
            )
            .group_by(Book.id, Book.title)
            .order_by(func.count(BorrowRecord.id).desc())
            .limit(5)
            .all()
        )

        # 押金池总额（PAID 押金）/ 待退押金（REFUND_PENDING + REFUNDING）
        deposit_pool = (
            self.db.query(func.coalesce(func.sum(DepositRecord.amount), 0))
            .filter(
                DepositRecord.status == DepositStatus.PAID,
                DepositRecord.is_deleted == 0,
            )
            .scalar()
        )
        deposit_refunding_count = (
            self.db.query(func.count(DepositRecord.id))
            .filter(
                DepositRecord.status.in_(
                    [DepositStatus.REFUND_PENDING, DepositStatus.REFUNDING]
                ),
                DepositRecord.is_deleted == 0,
            )
            .scalar()
            or 0
        )

        # 转化漏斗：各类型已支付订单数（去重孩子）
        funnel = {}
        for order_type, label in (
            (OrderType.PARENT_COURSE, "parent_course"),
            (OrderType.OBSERVATION, "observation"),
            (OrderType.OFFICIAL_MEMBER, "official_member"),
        ):
            funnel[label] = (
                self.db.query(func.count(func.distinct(Order.child_id)))
                .filter(
                    Order.type == order_type,
                    Order.pay_status == PayStatus.PAID,
                    Order.is_deleted == 0,
                )
                .scalar()
                or 0
            )

        return {
            "today_borrows": today_borrows,
            "today_returns": today_returns,
            "week_new_members": week_new_members,
            "week_lost_members": week_lost_members,
            "overdue_top_children": [
                {
                    "child_id": r.id,
                    "child_name": r.name,
                    "overdue_count": r.overdue_count,
                    "fine_total": str(r.fine_total),
                }
                for r in overdue_by_child
            ],
            "overdue_top_books": [
                {
                    "book_id": r.id,
                    "book_title": r.title,
                    "overdue_count": r.overdue_count,
                }
                for r in overdue_by_book
            ],
            "deposit_pool_total": str(deposit_pool or 0),
            "deposit_refunding_count": deposit_refunding_count,
            "conversion_funnel": funnel,
        }

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
