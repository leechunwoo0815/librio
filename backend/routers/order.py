# backend/routers/order.py
"""
[What] 订单API路由
[Why] 定义订单相关的API端点
[How] 使用FastAPI路由器
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.repositories.order_repo import OrderRepository
from backend.services.order_service import OrderService
from backend.schemas.order import (
    OrderCreate, OrderResponse, OrderPayRequest,
    OrderRefundRequest, OrderListResponse
)
from backend.middleware.auth import get_current_user
from backend.schemas.user import UserResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/order", tags=["订单"])


def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    """
    [What] 获取订单服务实例（依赖注入）
    [Why] FastAPI依赖注入模式
    [How] 创建仓库和服务实例
    """
    order_repo = OrderRepository(db)
    return OrderService(order_repo)


@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    order_service: OrderService = Depends(get_order_service),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    [What] 创建订单接口
    [Why] 用户下单
    [How] 调用订单服务创建订单
    """
    # 验证用户ID与当前登录用户一致
    if order_data.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权为其他用户创建订单")

    try:
        return order_service.create_order(order_data)
    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail="创建订单失败")


@router.get("/{order_no}", response_model=OrderResponse)
async def get_order(
    order_no: str,
    order_service: OrderService = Depends(get_order_service),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    [What] 获取订单详情接口
    [Why] 查询订单信息
    [How] 根据订单号查询
    """
    order = order_service.get_order_by_no(order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    # 验证订单属于当前用户
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此订单")

    return order


@router.get("/user/list", response_model=OrderListResponse)
async def get_user_orders(
    order_service: OrderService = Depends(get_order_service),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    [What] 获取用户订单列表接口
    [Why] 查询用户的所有订单
    [How] 根据用户ID查询
    """
    orders = order_service.get_user_orders(current_user.id)
    return OrderListResponse(
        total=len(orders),
        items=orders
    )


@router.post("/pay", response_model=OrderResponse)
async def pay_order(
    pay_data: OrderPayRequest,
    order_service: OrderService = Depends(get_order_service),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    [What] 支付订单接口
    [Why] 订单支付
    [How] 调用订单服务处理支付
    """
    # 先验证订单属于当前用户
    order = order_service.get_order_by_no(pay_data.order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权支付此订单")

    result = order_service.pay_order(pay_data.order_no, pay_data.payment_no)
    if not result:
        raise HTTPException(status_code=400, detail="支付失败，订单状态异常")

    return result


@router.post("/refund", response_model=OrderResponse)
async def refund_order(
    refund_data: OrderRefundRequest,
    order_service: OrderService = Depends(get_order_service),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    [What] 退款订单接口
    [Why] 订单退款
    [How] 调用订单服务处理退款
    """
    # 先验证订单属于当前用户
    order = order_service.get_order_by_no(refund_data.order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权退款此订单")

    result = order_service.refund_order(refund_data.order_no, refund_data.reason)
    if not result:
        raise HTTPException(status_code=400, detail="退款失败，订单状态异常")

    return result
