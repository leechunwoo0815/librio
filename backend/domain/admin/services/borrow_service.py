# backend/domain/admin/services/borrow_service.py
"""管理端借阅/押金/预约 Service — 从 AdminService 拆分出来的独立域服务。"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError
from backend.common.types import BorrowStatus
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

    def list_borrows(self, page: int = 1, page_size: int = 20, status: int | None = None) -> dict:
        """获取借阅列表 — 带分页"""
        from backend.domain.book.models import Book

        query = self.db.query(BorrowRecord).filter(BorrowRecord.is_deleted == 0)
        if status is not None:
            query = query.filter(BorrowRecord.status == status)

        total = query.count()
        records = query.order_by(
            BorrowRecord.borrow_time.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()

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
            result.append({
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
                "fine_amount": float(r.fine_amount) if r.fine_amount else 0,
            })

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
        }

    def list_deposits(self, page: int = 1, page_size: int = 20) -> dict:
        """获取押金列表 — 带分页"""
        total = self.db.query(DepositRecord).filter(DepositRecord.is_deleted == 0).count()

        records = self.db.query(DepositRecord).filter(
            DepositRecord.is_deleted == 0
        ).order_by(
            DepositRecord.create_time.desc()
        ).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        # 批量获取所有相关 child，避免 N+1 查询
        child_ids = list(set(r.child_id for r in records if r.child_id))
        children = {}
        if child_ids:
            for c in self.db.query(Child).filter(Child.id.in_(child_ids), Child.is_deleted == 0).all():
                children[c.id] = c.name

        result = []
        for r in records:
            result.append({
                "id": r.id,
                "child_id": r.child_id,
                "child_name": children.get(r.child_id),
                "amount": float(r.amount) if r.amount else 0,
                "status": r.status.name if hasattr(r.status, 'name') else str(r.status),
                "fine_amount": float(r.fine_amount) if hasattr(r, 'fine_amount') and r.fine_amount else 0,
                "create_time": r.create_time.isoformat() if r.create_time else None,
            })

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def list_reservations(self, page: int = 1, page_size: int = 20, status: str = None) -> dict:
        """获取预约列表 — 带分页"""
        from backend.domain.book.models import Book

        query = self.db.query(Reservation).filter(Reservation.is_deleted == 0)
        if status:
            query = query.filter(Reservation.status == status)

        total = query.count()
        reservations = query.order_by(
            Reservation.create_time.desc()
        ).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        # 批量查询 child 和 book，避免 N+1
        child_ids = list(set(r.child_id for r in reservations if r.child_id))
        book_ids = list(set(r.book_id for r in reservations if r.book_id))
        children = {}
        books = {}
        if child_ids:
            for c in self.db.query(Child).filter(Child.id.in_(child_ids), Child.is_deleted == 0).all():
                children[c.id] = c.name
        if book_ids:
            for b in self.db.query(Book).filter(Book.id.in_(book_ids), Book.is_deleted == 0).all():
                books[b.id] = b.title

        result = []
        for r in reservations:
            result.append({
                "id": r.id,
                "child_id": r.child_id,
                "child_name": children.get(r.child_id),
                "book_id": r.book_id,
                "book_title": books.get(r.book_id),
                "status": r.status,
                "create_time": r.create_time.isoformat() if r.create_time else None,
            })

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

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
