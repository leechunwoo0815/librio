# backend/schemas/order.py
"""
[What] 订单Pydantic模型
[Why] 用于API请求/响应数据验证
[How] 使用Pydantic定义数据结构
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class OrderCreate(BaseModel):
    """
    [What] 创建订单请求模型
    [Why] 验证创建订单的数据格式
    [How] 定义必填和可选字段
    """
    user_id: int = Field(..., description="用户ID")
    child_id: Optional[int] = Field(None, description="孩子ID")
    type: int = Field(..., description="订单类型：1-亲子课程，2-观察力训练，3-正式会员，4-押金")
    amount: Decimal = Field(..., gt=0, description="订单金额")
    remark: Optional[str] = Field(None, description="备注")


class OrderResponse(BaseModel):
    """
    [What] 订单响应模型
    [Why] API返回订单信息
    [How] 定义返回字段
    """
    id: int
    order_no: str
    user_id: int
    child_id: Optional[int]
    type: int
    amount: Decimal
    status: str
    payment_no: Optional[str]
    payment_time: Optional[datetime]
    remark: Optional[str]
    create_time: datetime

    class Config:
        from_attributes = True


class OrderPayRequest(BaseModel):
    """
    [What] 订单支付请求模型
    [Why] 验证支付请求数据
    [How] 定义支付相关字段
    """
    order_no: str = Field(..., description="订单号")
    payment_no: str = Field(..., description="支付流水号")


class OrderRefundRequest(BaseModel):
    """
    [What] 订单退款请求模型
    [Why] 验证退款请求数据
    [How] 定义退款相关字段
    """
    order_no: str = Field(..., description="订单号")
    reason: Optional[str] = Field(None, description="退款原因")


class OrderListResponse(BaseModel):
    """
    [What] 订单列表响应模型
    [Why] 返回用户订单列表
    [How] 定义列表结构
    """
    total: int
    items: list[OrderResponse]
