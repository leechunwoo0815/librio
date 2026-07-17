# backend/domain/admin/services/user_service.py
"""管理端用户 Service — 从 AdminService 拆分出来的独立域服务。"""

import secrets
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.types import BorrowStatus
from backend.domain.advancement.models import ReadingSubmission
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.child.schemas import ChildCreate, ChildUpdate
from backend.domain.order.models import Order
from backend.domain.admin.models import Venue
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
        user_ids = [u.id for u in users]
        all_children = (
            self.db.query(Child)
            .filter(Child.user_id.in_(user_ids), Child.is_deleted == 0)
            .all()
        )
        children_by_user = {}
        for c in all_children:
            children_by_user.setdefault(c.user_id, []).append(c)

        venue_ids = {c.venue_id for c in all_children if c.venue_id}
        venue_map = {}
        if venue_ids:
            venues = (
                self.db.query(Venue).filter(Venue.id.in_(venue_ids)).all()
            )
            venue_map = {v.id: v.name for v in venues}

        items = []
        for u in users:
            children = children_by_user.get(u.id, [])
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
                            "grade": c.grade,
                            "status": c.status,
                            "deposit_status": c.deposit_status,
                            "outstanding_fines": str(c.outstanding_fines or 0),
                            "ar_level": float(c.ar_level) if c.ar_level else None,
                            "member_expire_time": c.member_expire_time.isoformat()
                            if c.member_expire_time
                            else None,
                            "venue_name": venue_map.get(c.venue_id) if c.venue_id else None,
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

    def list_children(self, limit: int = 500, child_ids: list[int] | None = None) -> list[dict]:
        """获取孩子列表 — 借还场景下拉框专用"""
        query = (
            self.db.query(Child)
            .filter(Child.is_deleted == 0)
        )
        if child_ids is not None:
            if not child_ids:
                return []
            query = query.filter(Child.id.in_(child_ids))
        children = (
            query
            .order_by(Child.id.asc())
            .limit(limit)
            .all()
        )
        child_ids = [c.id for c in children]
        borrow_counts = dict(
            self.db.query(
                BorrowRecord.child_id,
                func.count(BorrowRecord.id),
            )
            .filter(
                BorrowRecord.child_id.in_(child_ids),
                BorrowRecord.status == BorrowStatus.BORROWING,
                BorrowRecord.is_deleted == 0,
            )
            .group_by(BorrowRecord.child_id)
            .all()
        )
        results = []
        for child in children:
            user = child.user
            results.append(
                {
                    "id": child.id,
                    "name": child.name,
                    "english_name": child.english_name,
                    "status": child.status,
                    "deposit_status": child.deposit_status,
                    "current_borrow_count": borrow_counts.get(child.id, 0),
                    "ar_level": float(child.ar_level) if child.ar_level else None,
                    "parent_name": user.parent_name if user else None,
                    "phone": user.phone if user else None,
                }
            )
        return results

    def search_children(self, keyword: str, child_ids: list[int] | None = None) -> list[dict]:
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
        if child_ids is not None:
            if not child_ids:
                return []
            q = q.filter(Child.id.in_(child_ids))

        children_list = q.all()
        child_ids = [c.id for c in children_list]
        borrow_counts = dict(
            self.db.query(
                BorrowRecord.child_id,
                func.count(BorrowRecord.id),
            )
            .filter(
                BorrowRecord.child_id.in_(child_ids),
                BorrowRecord.status == BorrowStatus.BORROWING,
                BorrowRecord.is_deleted == 0,
            )
            .group_by(BorrowRecord.child_id)
            .all()
        )
        results = []
        for child in children_list:
            results.append(
                {
                    "id": child.id,
                    "name": child.name,
                    "english_name": child.english_name,
                    "status": child.status,
                    "parent_name": child.user.parent_name if child.user else None,
                    "phone": child.user.phone if child.user else None,
                    "current_borrow_count": borrow_counts.get(child.id, 0),
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
        venue_ids = {c.venue_id for c in children if c.venue_id}
        venue_map = {}
        if venue_ids:
            venues = self.db.query(Venue).filter(Venue.id.in_(venue_ids)).all()
            venue_map = {v.id: v.name for v in venues}

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
                    "grade": c.grade,
                    "status": c.status,
                    "deposit_status": c.deposit_status,
                    "ar_level": float(c.ar_level) if c.ar_level else None,
                    "member_expire_time": c.member_expire_time.isoformat()
                    if c.member_expire_time
                    else None,
                    "total_reading_minutes": c.total_reading_minutes,
                    "total_books_finished": c.total_books_finished,
                    "current_streak_days": c.current_streak_days,
                    "venue_name": venue_map.get(c.venue_id) if c.venue_id else None,
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

    def update_user(self, user_id: int, data) -> dict:
        """更新用户/家长信息，允许同步更新首个孩子的状态"""
        user = (
            self.db.query(User).filter(User.id == user_id, User.is_deleted == 0).first()
        )
        if not user:
            raise NotFoundError("用户不存在")

        update_data = data.model_dump(exclude_unset=True)
        child_status = update_data.pop("child_status", None)

        if "parent_name" in update_data:
            user.parent_name = update_data["parent_name"]
        if "phone" in update_data:
            # 简单校验手机号唯一性
            existing = (
                self.db.query(User)
                .filter(User.phone == update_data["phone"], User.id != user_id)
                .first()
            )
            if existing:
                raise ValidationError("手机号已被其他用户使用")
            user.phone = update_data["phone"]

        if child_status is not None:
            first_child = (
                self.db.query(Child)
                .filter(Child.user_id == user_id, Child.is_deleted == 0)
                .order_by(Child.id.asc())
                .first()
            )
            if first_child:
                first_child.status = child_status

        self.db.commit()
        return {"success": True, "message": "用户信息更新成功"}

    def get_child_detail(self, child_id: int) -> dict:
        """孩子详情 — 基本信息 + 家长 + 借阅统计"""
        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")

        borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.is_deleted == 0,
            )
            .order_by(BorrowRecord.borrow_time.desc())
            .limit(50)
            .all()
        )
        total_borrows = len(borrows)
        current_borrows = sum(1 for b in borrows if b.status == 0)
        overdue_borrows = sum(1 for b in borrows if b.status == 2)

        user = child.user
        venue_name = None
        if child.venue_id:
            venue = self.db.query(Venue).filter(Venue.id == child.venue_id).first()
            venue_name = venue.name if venue else None
        return {
            "child": {
                "id": child.id,
                "name": child.name,
                "english_name": child.english_name,
                "age": child.age,
                "status": child.status,
                "ar_level": float(child.ar_level) if child.ar_level else None,
                "deposit_status": child.deposit_status,
                "outstanding_fines": str(child.outstanding_fines or 0),
                "member_expire_time": child.member_expire_time.isoformat()
                if child.member_expire_time
                else None,
                "total_reading_minutes": child.total_reading_minutes,
                "total_books_finished": child.total_books_finished,
                "current_streak_days": child.current_streak_days,
                "create_time": child.create_time.isoformat()
                if child.create_time
                else None,
                "venue_name": venue_name,
            },
            "parent": {
                "id": user.id if user else None,
                "parent_name": user.parent_name if user else None,
                "phone": user.phone if user else None,
            },
            "borrow_stats": {
                "total": total_borrows,
                "current": current_borrows,
                "overdue": overdue_borrows,
            },
        }

    def admin_create_child(self, user_id: int, data: ChildCreate) -> dict:
        """管理员创建孩子（为指定用户）"""
        user = self.db.query(User).filter(User.id == user_id, User.is_deleted == 0).first()
        if not user:
            raise NotFoundError("用户不存在")
        child = Child(
            user_id=user_id,
            name=data.name,
            english_name=data.english_name,
            age=data.age,
            grade=data.grade,
            venue_id=data.venue_id,
        )
        self.db.add(child)
        self.db.commit()
        self.db.refresh(child)
        return {"success": True, "child_id": child.id, "message": "孩子创建成功"}

    def admin_update_child(self, child_id: int, data: ChildUpdate) -> dict:
        """管理员更新孩子信息"""
        child = self.db.query(Child).filter(Child.id == child_id, Child.is_deleted == 0).first()
        if not child:
            raise NotFoundError("孩子不存在")
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(child, field, value)
        self.db.commit()
        return {"success": True, "message": "孩子更新成功"}

    def admin_delete_child(self, child_id: int) -> dict:
        """管理员删除孩子（软删除）"""
        child = self.db.query(Child).filter(Child.id == child_id, Child.is_deleted == 0).first()
        if not child:
            raise NotFoundError("孩子不存在")
        # 检查是否有未还书
        active_borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.is_deleted == 0,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
            )
            .count()
        )
        if active_borrows > 0:
            raise ValidationError(f"该孩子有 {active_borrows} 本未还书，请先归还后再删除")
        child.soft_delete()
        self.db.commit()
        return {"success": True, "message": "孩子已删除"}

    def admin_create_user(self, data) -> dict:
        """管理员创建用户（家长+可选孩子）"""
        from passlib.context import CryptContext

        # 检查手机号唯一性
        existing = self.db.query(User).filter(User.phone == data.phone, User.is_deleted == 0).first()
        if existing:
            raise ValidationError(f"手机号 {data.phone} 已存在")
        # 生成 synthetic openid（User 模型 openid 不可为空且唯一）
        synthetic_openid = f"admin_created_{data.phone}"
        existing_openid = self.db.query(User).filter(User.openid == synthetic_openid).first()
        if existing_openid:
            raise ValidationError("该手机号已创建过账号")
        # 密码：未提供则生成 12 位随机安全密码
        raw_password = data.password or secrets.token_urlsafe(12)
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = pwd_ctx.hash(raw_password)
        user = User(
            parent_name=data.parent_name,
            phone=data.phone,
            password=hashed,
            openid=synthetic_openid,
        )
        self.db.add(user)
        self.db.flush()
        # 可选同时创建孩子
        child_id = None
        if data.child_name:
            child = Child(
                user_id=user.id,
                name=data.child_name,
                age=data.child_age or 3,
                grade=data.child_grade or "未设置",
                venue_id=data.venue_id,
            )
            self.db.add(child)
            self.db.flush()
            child_id = child.id
        self.db.commit()
        return {
            "success": True,
            "message": "用户创建成功",
            "user_id": user.id,
            "child_id": child_id,
            "default_password": raw_password,
        }
