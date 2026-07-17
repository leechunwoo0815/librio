# backend/domain/admin/services/borrow_service.py
"""管理端借阅/押金/预约 Service — 从 AdminService 拆分出来的独立域服务。"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError
from backend.common.types import BorrowStatus, DepositStatus
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.reservation.models import Reservation
from backend.domain.user.models import User


class AdminBorrowService:
    """管理端借阅、押金、预约、罚款清零、孩子搜索。"""

    def __init__(self, db: Session):
        self.db = db

    def clear_child_fines(self, child_id: int, admin_id: int) -> dict:
        """管理员清零孩子罚款"""
        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")

        old_fines = child.outstanding_fines or 0
        child.outstanding_fines = 0
        self.db.commit()
        return {"success": True, "child_id": child_id, "cleared_amount": str(old_fines)}

    def list_borrows(
        self,
        page: int = 1,
        page_size: int = 20,
        status: int | None = None,
        child_ids: list[int] | None = None,
    ) -> dict:
        """获取借阅列表 — 带分页"""
        from backend.domain.book.models import Book

        query = self.db.query(BorrowRecord).filter(BorrowRecord.is_deleted == 0)
        if status is not None:
            query = query.filter(BorrowRecord.status == status)
        if child_ids is not None:
            if not child_ids:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_next": False,
                }
            query = query.filter(BorrowRecord.child_id.in_(child_ids))

        total = query.count()
        records = (
            query.order_by(BorrowRecord.borrow_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量查询 child 和 book
        child_ids = list(set(r.child_id for r in records if r.child_id))
        book_ids = list(set(r.book_id for r in records if r.book_id))
        children = {}
        books = {}
        if child_ids:
            for c in self.db.query(Child).filter(Child.id.in_(child_ids)).all():
                children[c.id] = c.name
        if book_ids:
            for b in self.db.query(Book).filter(Book.id.in_(book_ids)).all():
                books[b.id] = b.title

        result = []
        for r in records:
            result.append(
                {
                    "id": r.id,
                    "child_id": r.child_id,
                    "child_name": children.get(r.child_id),
                    "book_id": r.book_id,
                    "book_title": books.get(r.book_id),
                    "book_copy_id": r.book_copy_id,
                    "borrow_time": r.borrow_time.isoformat() if r.borrow_time else None,
                    "due_date": r.due_date.isoformat() if r.due_date else None,
                    "return_time": r.return_time.isoformat() if r.return_time else None,
                    "status": r.status,
                    "overdue_days": r.overdue_days or 0,
                    "fine_amount": str(r.fine_amount) if r.fine_amount else "0",
                }
            )

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
        }

    def list_deposits(
        self, page: int = 1, page_size: int = 20, child_ids: list[int] | None = None
    ) -> dict:
        """获取押金列表 — 带分页"""
        query = self.db.query(DepositRecord).filter(DepositRecord.is_deleted == 0)
        if child_ids is not None:
            if not child_ids:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_next": False,
                }
            query = query.filter(DepositRecord.child_id.in_(child_ids))
        total = query.count()
        records = (
            query.order_by(DepositRecord.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量获取所有相关 child，避免 N+1 查询
        child_ids = list(set(r.child_id for r in records if r.child_id))
        children = {}
        if child_ids:
            for c in (
                self.db.query(Child)
                .filter(Child.id.in_(child_ids), Child.is_deleted == 0)
                .all()
            ):
                children[c.id] = c.name

        result = []
        for r in records:
            # 将整型状态转为可读名称
            try:
                status_value = r.status
                if isinstance(status_value, int):
                    status_name = DepositStatus(status_value).name
                elif hasattr(status_value, "name"):
                    status_name = status_value.name
                else:
                    status_name = str(status_value).upper()
            except Exception:
                status_name = str(r.status)
            result.append(
                {
                    "id": r.id,
                    "child_id": r.child_id,
                    "child_name": children.get(r.child_id),
                    "amount": str(r.amount) if r.amount else "0",
                    "status": status_name,
                    "fine_amount": str(r.fine_amount)
                    if hasattr(r, "fine_amount") and r.fine_amount
                    else "0",
                    "create_time": r.create_time.isoformat() if r.create_time else None,
                }
            )

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def list_reservations(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str = None,
        child_ids: list[int] | None = None,
    ) -> dict:
        """获取预约列表 — 带分页"""
        from backend.domain.book.models import Book

        query = self.db.query(Reservation).filter(Reservation.is_deleted == 0)
        if child_ids is not None:
            if not child_ids:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_next": False,
                }
            query = query.filter(Reservation.child_id.in_(child_ids))
        if status:
            query = query.filter(Reservation.status == status)

        total = query.count()
        reservations = (
            query.order_by(Reservation.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量查询 child 和 book，避免 N+1
        child_ids = list(set(r.child_id for r in reservations if r.child_id))
        book_ids = list(set(r.book_id for r in reservations if r.book_id))
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
                books[b.id] = b.title

        result = []
        for r in reservations:
            result.append(
                {
                    "id": r.id,
                    "child_id": r.child_id,
                    "child_name": children.get(r.child_id),
                    "book_id": r.book_id,
                    "book_title": books.get(r.book_id),
                    "status": r.status,
                    "create_time": r.create_time.isoformat() if r.create_time else None,
                }
            )

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def _child_to_dict(self, child: Child) -> dict:
        """将孩子 ORM 对象转为借还场景需要的字典"""
        return {
            "id": child.id,
            "name": child.name,
            "english_name": child.english_name,
            "status": child.status,
            "parent_name": child.user.parent_name if child.user else None,
            "phone": child.user.phone if child.user else None,
            "current_borrow_count": self._child_borrow_count(child.id),
            "deposit_status": child.deposit_status,
            "ar_level": float(child.ar_level) if child.ar_level else None,
        }

    def _batch_borrow_counts(self, child_ids: list[int]) -> dict[int, int]:
        if not child_ids:
            return {}
        return dict(
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

    def _child_to_dict(self, child: Child, borrow_count: int = 0) -> dict:
        return {
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

    def list_children(
        self, limit: int = 500, child_ids: list[int] | None = None
    ) -> list[dict]:
        """列出所有可用孩子 — 用于扫码借还下拉框"""
        query = self.db.query(Child).filter(Child.is_deleted == 0)
        if child_ids is not None:
            if not child_ids:
                return []
            query = query.filter(Child.id.in_(child_ids))
        children = query.order_by(Child.id).limit(limit).all()
        counts = self._batch_borrow_counts([c.id for c in children])
        return [self._child_to_dict(c, counts.get(c.id, 0)) for c in children]

    def search_children(
        self, keyword: str, child_ids: list[int] | None = None
    ) -> list[dict]:
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

        children = q.all()
        counts = self._batch_borrow_counts([c.id for c in children])
        return [self._child_to_dict(c, counts.get(c.id, 0)) for c in children]
