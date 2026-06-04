# backend/repositories/order_repo.py
"""
[What] 订单数据访问层
[Why] 封装数据库操作，与业务逻辑解耦
[How] 使用SQLAlchemy ORM查询
"""

from sqlalchemy.orm import Session
from backend.models.order import Order
from typing import Optional


class OrderRepository:
    """
    [What] 订单仓库类
    [Why] 封装订单相关的数据库操作
    [How] 注入数据库会话，执行CRUD操作
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, order_id: int) -> Optional[Order]:
        """
        [What] 根据ID查询订单
        [Why] 获取订单详情
        [How] 使用SQLAlchemy查询
        """
        return self.db.query(Order).filter(
            Order.id == order_id,
            Order.is_deleted == 0
        ).first()

    def get_by_order_no(self, order_no: str) -> Optional[Order]:
        """
        [What] 根据订单号查询订单
        [Why] 订单号是业务唯一标识
        [How] 使用SQLAlchemy查询
        """
        return self.db.query(Order).filter(
            Order.order_no == order_no,
            Order.is_deleted == 0
        ).first()

    def get_by_user_id(self, user_id: int) -> list[Order]:
        """
        [What] 根据用户ID查询订单列表
        [Why] 获取用户的所有订单
        [How] 使用SQLAlchemy查询
        """
        return self.db.query(Order).filter(
            Order.user_id == user_id,
            Order.is_deleted == 0
        ).order_by(Order.create_time.desc()).all()

    def create(self, order: Order) -> Order:
        """
        [What] 创建订单
        [Why] 新建订单
        [How] 添加到数据库并提交
        """
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def update(self, order: Order) -> Order:
        """
        [What] 更新订单
        [Why] 修改订单信息
        [How] 提交数据库更新
        """
        self.db.commit()
        self.db.refresh(order)
        return order
