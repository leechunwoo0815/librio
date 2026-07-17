# backend/domain/admin/services/order_service.py
"""管理端订单 Service — 从 AdminService 拆分出来的独立域服务。"""

import logging
import secrets
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.types import PayStatus
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.order.schemas import OrderCreate
from backend.domain.order.service import OrderService as DomainOrderService
from backend.domain.refund.models import RefundApplication
from backend.domain.user.models import User

logger = logging.getLogger(__name__)


class AdminOrderService:
    """管理端订单查询与代客创建/状态更新。"""

    def __init__(self, db: Session):
        self.db = db

    def list_orders_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        order_type: int = None,
        pay_status: int = None,
        date_from: str = None,
        date_to: str = None,
        search: str = None,
    ) -> dict:
        """分页查询订单列表 — 支持多条件筛选"""

        q = self.db.query(Order).filter(Order.is_deleted == 0)

        if order_type is not None:
            q = q.filter(Order.type == order_type)
        if pay_status is not None:
            q = q.filter(Order.pay_status == pay_status)
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                q = q.filter(Order.create_time >= dt_from)
            except ValueError:
                logger.warning("Invalid date_from format: %s", date_from)
        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to)
                q = q.filter(Order.create_time <= dt_to)
            except ValueError:
                logger.warning("Invalid date_to format: %s", date_to)
        if search:
            user_ids = (
                self.db.query(User.id).filter(User.phone.like(f"%{search}%")).subquery()
            )
            q = q.filter(
                or_(
                    Order.order_no.like(f"%{search}%"),
                    Order.user_id.in_(user_ids),
                )
            )

        total = q.count()
        orders = (
            q.order_by(Order.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量查询所有相关 user 和 child，避免 N+1
        user_ids = list(set(o.user_id for o in orders if o.user_id))
        child_ids = list(set(o.child_id for o in orders if o.child_id))

        users = {}
        if user_ids:
            for u in (
                self.db.query(User)
                .filter(User.id.in_(user_ids), User.is_deleted == 0)
                .all()
            ):
                users[u.id] = u

        children = {}
        if child_ids:
            for c in (
                self.db.query(Child)
                .filter(Child.id.in_(child_ids), Child.is_deleted == 0)
                .all()
            ):
                children[c.id] = c

        items = []
        for o in orders:
            user = users.get(o.user_id)
            child = children.get(o.child_id)
            items.append(
                {
                    "id": o.id,
                    "order_no": o.order_no,
                    "user_id": o.user_id,
                    "child_id": o.child_id,
                    "type": o.type,
                    "amount": str(o.amount or 0),
                    "pay_status": o.pay_status,
                    "pay_time": o.pay_time.isoformat() if o.pay_time else None,
                    "create_time": o.create_time.isoformat() if o.create_time else None,
                    "user_phone": user.phone if user else None,
                    "user_name": user.parent_name if user else None,
                    "child_name": child.name if child else None,
                    "refund_status": o.refund_status,
                }
            )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def get_order(self, order_no: str) -> dict:
        """获取订单详情"""
        order = (
            self.db.query(Order)
            .filter(Order.order_no == order_no, Order.is_deleted == 0)
            .first()
        )
        if not order:
            raise NotFoundError("订单不存在")

        return {
            "id": order.id,
            "order_no": order.order_no,
            "user_id": order.user_id,
            "child_id": order.child_id,
            "amount": str(order.amount) if order.amount else "0",
            "status": order.status,
            "create_time": order.create_time.isoformat() if order.create_time else None,
        }

    def get_order_refund(self, order_no: str) -> dict:
        """按订单号查询退款申请"""
        order = (
            self.db.query(Order)
            .filter(Order.order_no == order_no, Order.is_deleted == 0)
            .first()
        )
        if not order:
            raise NotFoundError("订单不存在")

        refund = (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.order_id == order.id,
                RefundApplication.is_deleted == 0,
            )
            .first()
        )

        if not refund:
            return {
                "exists": False,
                "order_no": order_no,
                "pay_status": order.pay_status,
            }

        return {
            "exists": True,
            "refund_id": refund.id,
            "order_no": order_no,
            "amount": str(refund.amount or 0),
            "refund_amount": str(refund.refund_amount or 0),
            "reason": refund.reason or "",
            "status": refund.status,
            "used_days": refund.used_days or 0,
            "create_time": refund.create_time.isoformat()
            if refund.create_time
            else None,
        }

    def create_order(self, data: dict) -> dict:
        """管理员代客创建订单（支持直接标记已支付）"""
        child_id = data.get("child_id")
        order_type = data.get("order_type")
        remark = data.get("remark", "")

        if not child_id or not order_type:
            raise ValidationError("孩子ID和订单类型必填")

        # 获取孩子的 user_id
        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")

        service = DomainOrderService(self.db)
        order_data = OrderCreate(child_id=child_id, type=order_type, remark=remark)
        result = service.create_order(child.user_id, order_data)
        # 管理员输入的金额始终覆盖打折价
        amount = data.get("amount")
        pay_type = data.get("pay_type")
        order_no = (
            result.get("order_no")
            if isinstance(result, dict)
            else getattr(result, "order_no", None)
        )
        if order_no:
            order = (
                self.db.query(Order)
                .filter(Order.order_no == order_no, Order.is_deleted == 0)
                .first()
            )
            if order:
                if amount is not None:
                    order.amount = amount
                if pay_type is not None:
                    order.pay_type = pay_type
                    order.pay_status = PayStatus.PAID
                    order.pay_time = datetime.now()
                self.db.commit()
        return result.model_dump() if hasattr(result, "model_dump") else result

    def create_offline_order(self, data: dict) -> dict:
        """线下创建用户+订单（兜底场景）"""
        from passlib.context import CryptContext

        # 检查手机号
        existing = (
            self.db.query(User)
            .filter(User.phone == data["phone"], User.is_deleted == 0)
            .first()
        )
        if existing:
            raise ValidationError(f"手机号 {data['phone']} 已存在")
        # 创建用户
        synthetic_openid = f"admin_created_{data['phone']}"
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        raw_password = secrets.token_urlsafe(12)
        hashed = pwd_ctx.hash(raw_password)
        user = User(
            parent_name=data["parent_name"],
            phone=data["phone"],
            password=hashed,
            openid=synthetic_openid,
        )
        self.db.add(user)
        self.db.flush()
        # 创建孩子
        child = Child(
            user_id=user.id,
            name=data["child_name"],
            age=data["child_age"],
            grade=data["child_grade"],
            venue_id=data.get("venue_id"),
        )
        self.db.add(child)
        self.db.flush()
        # 创建订单
        order = Order(
            order_no=self._generate_order_no(),
            user_id=user.id,
            child_id=child.id,
            type=data["order_type"],
            amount=data.get("amount") or 0,
            pay_status=PayStatus.PAID
            if data.get("amount") and data.get("pay_type")
            else PayStatus.PENDING,
            pay_type=data.get("pay_type"),
            pay_time=datetime.now()
            if data.get("amount") and data.get("pay_type")
            else None,
            remark=data.get("remark", ""),
        )
        self.db.add(order)
        self.db.commit()
        return {
            "success": True,
            "message": "订单创建成功",
            "order_no": order.order_no,
            "user_id": user.id,
            "child_id": child.id,
            "amount": str(order.amount),
            "pay_type": order.pay_type,
            "default_password": raw_password,
        }

    def _generate_order_no(self) -> str:
        """生成订单号: MW + 时间戳 + 4位随机数"""
        import random

        ts = str(int(datetime.now().timestamp() * 1000))
        rand = str(random.randint(1000, 9999))
        return f"MW{ts}{rand}"

    def update_order_status(self, order_no: str, data: dict) -> dict:
        """更新订单状态"""
        order = (
            self.db.query(Order)
            .filter(Order.order_no == order_no, Order.is_deleted == 0)
            .first()
        )
        if not order:
            raise NotFoundError("订单不存在")

        new_status = data.get("pay_status")
        if new_status is not None:
            order.pay_status = new_status
            if new_status == PayStatus.PAID:
                order.pay_time = datetime.now()

        self.db.commit()
        return {"success": True, "message": "订单状态已更新"}

    def delete_order(self, order_no: str) -> dict:
        """删除订单（软删除）"""
        order = (
            self.db.query(Order)
            .filter(Order.order_no == order_no, Order.is_deleted == 0)
            .first()
        )
        if not order:
            raise NotFoundError("订单不存在")

        order.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "订单已删除"}
