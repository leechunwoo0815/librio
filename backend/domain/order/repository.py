# backend/domain/order/repository.py
"""订单域数据访问层"""

import time

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.types import PayStatus
from backend.domain.order.models import Order


class OrderRepository(BaseRepository[Order]):
    def __init__(self, db: Session):
        super().__init__(db, Order)

    def get_by_order_no(self, order_no: str) -> Order | None:
        return self.get_by_field("order_no", order_no)

    def get_by_user_id(
        self, user_id: int, page: int = 1, page_size: int = 10
    ) -> tuple[list[Order], int]:
        q = self.db.query(Order).filter(Order.user_id == user_id, Order.is_deleted == 0)
        total = q.count()
        offset = (page - 1) * page_size
        orders = (
            q.order_by(Order.create_time.desc()).offset(offset).limit(page_size).all()
        )
        return orders, total

    def generate_order_no(self) -> str:
        """生成唯一订单号: MW + 时间戳 + 4位随机"""
        import random

        return f"MW{int(time.time() * 1000)}{random.randint(1000, 9999)}"

    def count_pending_or_paid_by_child_and_type(
        self, child_id: int, order_type: int
    ) -> int:
        return (
            self.db.query(Order)
            .filter(
                Order.child_id == child_id,
                Order.type == order_type,
                Order.pay_status.in_([PayStatus.PENDING, PayStatus.PAID]),
                Order.is_deleted == 0,
            )
            .count()
        )
