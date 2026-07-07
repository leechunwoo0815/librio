# backend/domain/admin/services/user_service.py
"""管理端用户 Service — 从 AdminService 拆分出来的独立域服务。"""

from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.exceptions import NotFoundError
from backend.common.types import BorrowStatus
from backend.domain.advancement.models import ReadingSubmission
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.user.models import User


class AdminUserService:
    """管理端用户/孩子查询与详情聚合。"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = BaseRepository(db, User)
        self.child_repo = BaseRepository(db, Child)
        self.order_repo = BaseRepository(db, Order)

    def list_users_with_children(
        self, search: str = None, page: int = 1, page_size: int = 20
    ) -> dict:
        """分页查询用户+孩子列表 — 支持家长姓名、手机号、孩子姓名搜索"""
        q = self.db.query(User).filter(User.is_deleted == 0)
        if search:
            user_ids_with_matching_child = (
                self.db.query(Child.user_id)
                .filter(
                    Child.is_deleted == 0,
                    Child.name.like(f"%{search}%"),
                )
                .subquery()
            )
            q = q.filter(
                or_(
                    User.phone.like(f"%{search}%"),
                    User.parent_name.like(f"%{search}%"),
                    User.id.in_(user_ids_with_matching_child),
                )
            )
        total = q.count()
        users = (
            q.order_by(User.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = []
        for u in users:
            children = (
                self.db.query(Child)
                .filter(
                    Child.user_id == u.id,
                    Child.is_deleted == 0,
                )
                .all()
            )
            items.append(
                {
                    "id": u.id,
                    "phone": u.phone,
                    "parent_name": u.parent_name or "未设置",
                    "avatar": u.avatar,
                    "create_time": u.create_time.isoformat() if u.create_time else None,
                    "children_count": len(children),
                    "children": [
                        {
                            "id": c.id,
                            "name": c.name,
                            "english_name": c.english_name,
                            "age": c.age,
                            "status": c.status,
                            "deposit_status": c.deposit_status,
                            "outstanding_fines": float(c.outstanding_fines or 0),
                            "ar_level": float(c.ar_level) if c.ar_level else None,
                            "member_expire_time": c.member_expire_time.isoformat()
                            if c.member_expire_time
                            else None,
                        }
                        for c in children
                    ],
                }
            )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def list_pending_submissions(self) -> list:
        """获取待审核提交列表"""
        subs = (
            self.db.query(ReadingSubmission)
            .filter(
                ReadingSubmission.status == 0,
                ReadingSubmission.is_deleted == 0,
            )
            .order_by(ReadingSubmission.create_time.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "id": s.id,
                "child_id": s.child_id,
                "book_id": s.book_id,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            }
            for s in subs
        ]

    def search_children(self, keyword: str) -> list[dict]:
        """搜索孩子 — 借还场景专用，返回孩子+家长+借阅信息"""
        q = (
            self.db.query(Child)
            .join(User, Child.user_id == User.id)
            .filter(
                Child.is_deleted == 0,
                or_(
                    Child.name.like(f"%{keyword}%"),
                    Child.english_name.like(f"%{keyword}%"),
                    User.phone.like(f"%{keyword}%"),
                    User.parent_name.like(f"%{keyword}%"),
                ),
            )
            .limit(10)
        )

        results = []
        for child in q.all():
            borrow_count = (
                self.db.query(BorrowRecord)
                .filter(
                    BorrowRecord.child_id == child.id,
                    BorrowRecord.status == BorrowStatus.BORROWING,
                    BorrowRecord.is_deleted == 0,
                )
                .count()
            )
            results.append(
                {
                    "id": child.id,
                    "name": child.name,
                    "english_name": child.english_name,
                    "status": child.status,
                    "parent_name": child.user.parent_name if child.user else None,
                    "phone": child.user.phone if child.user else None,
                    "current_borrow_count": borrow_count,
                    "deposit_status": child.deposit_status,
                    "ar_level": float(child.ar_level) if child.ar_level else None,
                }
            )
        return results

    def get_user_detail(self, user_id: int) -> dict:
        """用户详情 — 家长信息+孩子列表+订单+借阅+退款"""
        from backend.domain.refund.models import RefundApplication

        user = (
            self.db.query(User).filter(User.id == user_id, User.is_deleted == 0).first()
        )
        if not user:
            raise NotFoundError("用户不存在")

        children = (
            self.db.query(Child)
            .filter(Child.user_id == user_id, Child.is_deleted == 0)
            .all()
        )
        orders = (
            self.db.query(Order)
            .filter(Order.user_id == user_id, Order.is_deleted == 0)
            .order_by(Order.create_time.desc())
            .limit(50)
            .all()
        )
        borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id.in_([c.id for c in children]) if children else [],
                BorrowRecord.is_deleted == 0,
            )
            .order_by(BorrowRecord.borrow_time.desc())
            .limit(50)
            .all()
            if children
            else []
        )
        refunds = (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.user_id == user_id, RefundApplication.is_deleted == 0
            )
            .all()
        )

        total_borrows = len(borrows)
        current_borrows = sum(1 for b in borrows if b.status == 0)
        overdue_borrows = sum(1 for b in borrows if b.status == 2)
        total_spent = str(
            sum(Decimal(str(o.amount)) for o in orders if o.pay_status == 1)
        )

        return {
            "user": {
                "id": user.id,
                "parent_name": user.parent_name or "未设置",
                "phone": user.phone,
                "avatar": user.avatar,
                "create_time": user.create_time.isoformat()
                if user.create_time
                else None,
            },
            "children": [
                {
                    "id": c.id,
                    "name": c.name,
                    "english_name": c.english_name,
                    "age": c.age,
                    "status": c.status,
                    "deposit_status": c.deposit_status,
                    "ar_level": float(c.ar_level) if c.ar_level else None,
                    "member_expire_time": c.member_expire_time.isoformat()
                    if c.member_expire_time
                    else None,
                    "total_reading_minutes": c.total_reading_minutes,
                    "total_books_finished": c.total_books_finished,
                    "current_streak_days": c.current_streak_days,
                }
                for c in children
            ],
            "orders": [
                {
                    "id": o.id,
                    "order_no": o.order_no,
                    "type": o.type,
                    "amount": str(o.amount),
                    "pay_status": o.pay_status,
                    "create_time": o.create_time.isoformat() if o.create_time else None,
                    "pay_time": o.pay_time.isoformat() if o.pay_time else None,
                }
                for o in orders
            ],
            "borrow_stats": {
                "total": total_borrows,
                "current": current_borrows,
                "overdue": overdue_borrows,
            },
            "refunds": [
                {
                    "id": r.id,
                    "amount": str(r.refund_amount or 0),
                    "status": r.status,
                    "create_time": r.create_time.isoformat() if r.create_time else None,
                }
                for r in refunds
            ],
            "summary": {
                "total_spent": total_spent,
                "children_count": len(children),
            },
        }
