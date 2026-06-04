# backend/services/order_service.py
"""
[What] 订单业务逻辑层
[Why] 封装订单相关的业务规则
[How] 调用仓库层，实现业务逻辑
"""

from datetime import datetime
from backend.repositories.order_repo import OrderRepository
from backend.schemas.order import OrderCreate, OrderResponse
from backend.models.order import Order
from typing import Optional
import logging
import random
import string

logger = logging.getLogger(__name__)


class OrderService:
    """
    [What] 订单服务类
    [Why] 封装订单业务逻辑
    [How] 注入仓库层，实现业务规则
    """

    def __init__(self, order_repo: OrderRepository):
        self.order_repo = order_repo

    def generate_order_no(self) -> str:
        """
        [What] 生成订单号
        [Why] 订单号需要唯一且可读
        [How] 格式：MW + 8位日期 + 5位随机数
        """
        date_str = datetime.now().strftime("%Y%m%d")
        random_str = ''.join(random.choices(string.digits, k=5))
        return f"MW{date_str}{random_str}"

    def create_order(self, order_data: OrderCreate) -> OrderResponse:
        """
        [What] 创建订单
        [Why] 订单创建业务逻辑
        [How] 生成订单号，创建订单记录
        """
        logger.info(f"Creating order for user {order_data.user_id}, type={order_data.type}")

        # 生成订单号
        order_no = self.generate_order_no()

        # 创建订单对象
        order = Order(
            order_no=order_no,
            user_id=order_data.user_id,
            child_id=order_data.child_id,
            type=order_data.type,
            amount=order_data.amount,
            status="pending",
            remark=order_data.remark,
        )

        # 保存到数据库
        created_order = self.order_repo.create(order)
        logger.info(f"Order created successfully: {created_order.order_no}")

        return OrderResponse.model_validate(created_order)

    def get_order_by_id(self, order_id: int) -> Optional[OrderResponse]:
        """
        [What] 根据ID获取订单
        [Why] 查询订单详情
        [How] 调用仓库层查询
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            return None
        return OrderResponse.model_validate(order)

    def get_order_by_no(self, order_no: str) -> Optional[OrderResponse]:
        """
        [What] 根据订单号获取订单
        [Why] 查询订单详情
        [How] 调用仓库层查询
        """
        order = self.order_repo.get_by_order_no(order_no)
        if not order:
            return None
        return OrderResponse.model_validate(order)

    def get_user_orders(self, user_id: int) -> list[OrderResponse]:
        """
        [What] 获取用户订单列表
        [Why] 查询用户的所有订单
        [How] 调用仓库层查询
        """
        orders = self.order_repo.get_by_user_id(user_id)
        return [OrderResponse.model_validate(order) for order in orders]

    def update_order_status(self, order_id: int, status: str) -> Optional[OrderResponse]:
        """
        [What] 更新订单状态
        [Why] 订单状态变更（支付、退款等）
        [How] 查询订单，更新状态
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            return None

        order.status = status
        updated_order = self.order_repo.update(order)
        logger.info(f"Order {order.order_no} status updated to {status}")

        return OrderResponse.model_validate(updated_order)

    def pay_order(self, order_no: str, payment_no: str) -> Optional[OrderResponse]:
        """
        [What] 支付订单
        [Why] 订单支付业务逻辑
        [How] 验证订单状态，更新支付信息
        """
        order = self.order_repo.get_by_order_no(order_no)
        if not order:
            logger.warning(f"Order not found: {order_no}")
            return None

        if order.status != "pending":
            logger.warning(f"Order {order_no} is not pending, current status: {order.status}")
            return None

        order.status = "paid"
        order.payment_no = payment_no
        order.payment_time = datetime.now()

        updated_order = self.order_repo.update(order)
        logger.info(f"Order {order_no} paid successfully")

        return OrderResponse.model_validate(updated_order)

    def refund_order(self, order_no: str, reason: Optional[str] = None) -> Optional[OrderResponse]:
        """
        [What] 退款订单
        [Why] 订单退款业务逻辑
        [How] 验证订单状态，更新退款信息
        """
        order = self.order_repo.get_by_order_no(order_no)
        if not order:
            logger.warning(f"Order not found: {order_no}")
            return None

        if order.status != "paid":
            logger.warning(f"Order {order_no} cannot be refunded, current status: {order.status}")
            return None

        order.status = "refunded"
        order.remark = reason or order.remark

        updated_order = self.order_repo.update(order)
        logger.info(f"Order {order_no} refunded successfully")

        return OrderResponse.model_validate(updated_order)
