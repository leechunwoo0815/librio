# backend/domain/admin/services/refund_service.py
"""管理端退款 Service — 从 AdminService 拆分出来的独立域服务。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError
from backend.common.types import AdminRole
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication


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

        # F52：金额公式在 OrderService.calculate_refund（此前 hasattr 恒 False 退回全额的死代码）
        from backend.domain.order.service import OrderService

        calc = OrderService(self.db).calculate_refund(order.id, used_days)
        refund_amount = calc.get("refund_amount") or order.amount

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
            # F52：审核通过≠钱已退——只置"退款中"，实际打款由网关执行链路完成
            order.refund_status = 1
        self.db.commit()
        self.db.refresh(refund)
        msg = (
            "退款已自动通过，正在打款" if is_admin else "退款申请已提交，等待管理员审核"
        )
        return {
            "success": True,
            "refund_id": refund.id,
            "message": msg,
            "status": refund.status,
        }
