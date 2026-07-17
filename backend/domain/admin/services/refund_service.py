# backend/domain/admin/services/refund_service.py
"""管理端退款 Service — 从 AdminService 拆分出来的独立域服务。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.types import AdminRole, PayStatus
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.refund.service import RefundService


class AdminRefundService:
    """管理端退款申请列表、审核、代客发起。"""

    def __init__(self, db: Session):
        self.db = db

    def list_refunds(
        self, page: int = 1, page_size: int = 20, status: str = None
    ) -> dict:
        """获取退款列表 — 带分页"""
        query = self.db.query(RefundApplication).filter(
            RefundApplication.is_deleted == 0
        )
        if status:
            query = query.filter(RefundApplication.status == status)

        total = query.count()
        refunds = (
            query.order_by(RefundApplication.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量查询 order，避免 N+1
        order_ids = list(set(r.order_id for r in refunds if r.order_id))
        orders = {}
        if order_ids:
            for o in (
                self.db.query(Order)
                .filter(Order.id.in_(order_ids), Order.is_deleted == 0)
                .all()
            ):
                orders[o.id] = o

        result = []
        for r in refunds:
            order = orders.get(r.order_id)
            result.append(
                {
                    "id": r.id,
                    "order_id": r.order_id,
                    "order_no": order.order_no if order else None,
                    "amount": str(r.amount) if r.amount else "0",
                    "reason": r.reason,
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

    def approve_refund(self, refund_id: int, data) -> dict:
        """批准退款"""
        refund = (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.id == refund_id, RefundApplication.is_deleted == 0
            )
            .first()
        )
        if not refund:
            raise NotFoundError("退款申请不存在")

        if refund.status != RefundApplication.STATUS_PENDING:
            raise ValidationError("退款申请已处理")

        order = (
            self.db.query(Order)
            .filter(Order.id == refund.order_id, Order.is_deleted == 0)
            .first()
        )
        if not order:
            raise NotFoundError("关联订单不存在")

        # 更新退款状态
        refund.status = RefundApplication.STATUS_APPROVED
        refund.review_comment = data.get("comment", "")
        refund.review_time = datetime.now()

        # 更新订单状态
        order.pay_status = PayStatus.REFUNDED

        self.db.commit()
        return {"success": True, "message": "退款已批准"}

    def get_refund_and_order(self, refund_id: int) -> tuple:
        """获取退款申请和关联订单"""
        refund = (
            self.db.query(RefundApplication)
            .filter(RefundApplication.id == refund_id)
            .first()
        )
        if not refund:
            raise NotFoundError("退款申请不存在")

        order = None
        if refund.order_id:
            order = self.db.query(Order).filter(Order.id == refund.order_id).first()

        return refund, order

    def create_refund(self, order_no: str, data: dict, admin=None) -> dict:
        """管理员代客发起退款申请（超级管理员自动审核通过）"""
        order = (
            self.db.query(Order)
            .filter(Order.order_no == order_no, Order.is_deleted == 0)
            .first()
        )
        if not order:
            raise NotFoundError("订单不存在")

        reason = data.get("reason", "管理员代发起退款")
        used_days = data.get("used_days", 0)
        refund_service = RefundService(self.db)

        refund_amount = (
            refund_service.calculate_refund(order.id, used_days)
            if hasattr(refund_service, "calculate_refund")
            else order.amount
        )
        if not refund_amount:
            refund_amount = order.amount

        is_admin = admin and getattr(admin, "role", None) == AdminRole.ADMIN
        refund = RefundApplication(
            order_id=order.id,
            user_id=order.user_id,
            child_id=order.child_id,
            amount=order.amount,
            refund_amount=Decimal(str(refund_amount)),
            used_days=used_days,
            reason=reason,
            status=RefundApplication.STATUS_APPROVED
            if is_admin
            else RefundApplication.STATUS_PENDING,
            reviewer_id=admin.id if is_admin else None,
            review_time=datetime.now() if is_admin else None,
        )
        self.db.add(refund)
        if is_admin:
            order.pay_status = PayStatus.REFUNDED
        self.db.commit()
        self.db.refresh(refund)
        msg = "退款已自动通过" if is_admin else "退款申请已提交，等待管理员审核"
        return {"success": True, "refund_id": refund.id, "message": msg}
