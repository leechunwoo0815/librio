# backend/domain/admin/services/export_service.py
"""管理端批量导出 Service — 从 AdminService 拆分出来的独立域服务。"""

import csv
import io

from sqlalchemy.orm import Session

from backend.common.exceptions import ValidationError
from backend.domain.advancement.models import Quiz
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.user.models import User


class AdminExportService:
    """管理端数据导出：图书、用户、订单、测评结果、活动报名。"""

    def __init__(self, db: Session):
        self.db = db

    def export_data(self, module: str) -> tuple[str, str]:
        """导出数据为 CSV（PC-020）

        Returns:
            (csv_content, filename) — 路由层包装为 StreamingResponse
        """
        from backend.domain.book.models import Book

        model_map = {
            "books": (
                Book,
                [
                    "id",
                    "isbn",
                    "title",
                    "author",
                    "ar_value",
                    "word_count",
                    "total_stock",
                    "available_stock",
                ],
            ),
            "users": (User, ["id", "phone", "parent_name", "openid", "create_time"]),
            "orders": (
                Order,
                [
                    "id",
                    "order_no",
                    "user_id",
                    "child_id",
                    "type",
                    "amount",
                    "pay_status",
                    "create_time",
                ],
            ),
        }

        if module == "quiz_results":
            return self._export_quiz_results()

        if module == "activity_enrollments":
            return self._export_activity_enrollments()

        if module not in model_map:
            raise ValidationError(f"不支持导出: {module}")

        Model, fields = model_map[module]
        items = self.db.query(Model).filter(Model.is_deleted == 0).limit(10000).all()

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for item in items:
            row = {}
            for f in fields:
                val = getattr(item, f, None)
                row[f] = str(val) if val is not None else ""
            writer.writerow(row)

        return output.getvalue(), f"{module}_export.csv"

    def _export_quiz_results(self) -> tuple[str, str]:
        """导出测评结果"""
        from backend.domain.book.models import Book

        quizzes = (
            self.db.query(Quiz)
            .filter(Quiz.is_deleted == 0)
            .order_by(Quiz.create_time.desc())
            .limit(10000)
            .all()
        )

        # 批量查询所有相关 child 和 book，避免 N+1
        child_ids = list(set(q.child_id for q in quizzes if q.child_id))
        book_ids = list(set(q.book_id for q in quizzes if q.book_id))

        children = {}
        if child_ids:
            for c in (
                self.db.query(Child)
                .filter(Child.id.in_(child_ids), Child.is_deleted == 0)
                .all()
            ):
                children[c.id] = c

        books = {}
        if book_ids:
            for b in (
                self.db.query(Book)
                .filter(Book.id.in_(book_ids), Book.is_deleted == 0)
                .all()
            ):
                books[b.id] = b

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "quiz_id",
                "child_name",
                "book_title",
                "total_questions",
                "correct_count",
                "score",
                "status",
                "create_time",
            ]
        )
        for q in quizzes:
            child = children.get(q.child_id)
            book = books.get(q.book_id)
            writer.writerow(
                [
                    q.id,
                    child.name if child else "",
                    book.title if book else "",
                    q.total_questions,
                    q.correct_count,
                    q.score,
                    q.status,
                    q.create_time.isoformat() if q.create_time else "",
                ]
            )

        return output.getvalue(), "quiz_results_export.csv"

    def _export_activity_enrollments(self) -> tuple[str, str]:
        """导出活动报名名单"""
        from backend.domain.activity.models import ActivityEnrollment, Activity

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "enrollment_id",
                "activity_title",
                "child_name",
                "ticket_code",
                "status",
                "sign_in_time",
                "create_time",
            ]
        )
        enrollments = (
            self.db.query(ActivityEnrollment)
            .filter(ActivityEnrollment.is_deleted == 0)
            .limit(10000)
            .all()
        )

        # 批量查询所有相关 child 和 activity，避免 N+1
        child_ids = list(set(e.child_id for e in enrollments if e.child_id))
        activity_ids = list(set(e.activity_id for e in enrollments if e.activity_id))

        children = {}
        if child_ids:
            for c in (
                self.db.query(Child)
                .filter(Child.id.in_(child_ids), Child.is_deleted == 0)
                .all()
            ):
                children[c.id] = c

        activities = {}
        if activity_ids:
            for a in (
                self.db.query(Activity)
                .filter(Activity.id.in_(activity_ids), Activity.is_deleted == 0)
                .all()
            ):
                activities[a.id] = a

        for e in enrollments:
            child = children.get(e.child_id)
            activity = activities.get(e.activity_id)
            writer.writerow(
                [
                    e.id,
                    activity.title if activity else "",
                    child.name if child else "",
                    e.ticket_code or "",
                    e.status,
                    e.sign_in_time.isoformat() if e.sign_in_time else "",
                    e.create_time.isoformat() if e.create_time else "",
                ]
            )

        return output.getvalue(), "activity_enrollments_export.csv"
