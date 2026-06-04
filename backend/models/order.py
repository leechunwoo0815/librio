# backend/models/order.py
"""
[What] 订单模型
[Why] 定义订单表结构
[How] 使用SQLAlchemy ORM映射
"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, SmallInteger, Numeric, Integer
from backend.database import Base


class Order(Base):
    """
    [What] 订单模型类
    [Why] 映射到数据库的order表
    [How] 继承Base，定义表结构
    """
    __tablename__ = "order"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment="主键")
    order_no = Column(String(32), nullable=False, unique=True, index=True, comment="订单号")
    user_id = Column(BigInteger, nullable=False, index=True, comment="用户ID")
    child_id = Column(BigInteger, nullable=True, comment="孩子ID")
    type = Column(SmallInteger, nullable=False, comment="订单类型：1-亲子课程，2-观察力训练，3-正式会员，4-押金")
    amount = Column(Numeric(10, 2), nullable=False, comment="订单金额")
    status = Column(String(20), nullable=False, default="pending", comment="订单状态：pending-待支付，paid-已支付，refunded-已退款，cancelled-已取消")
    payment_no = Column(String(64), nullable=True, comment="支付流水号")
    payment_time = Column(DateTime, nullable=True, comment="支付时间")
    remark = Column(String(255), nullable=True, comment="备注")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    is_deleted = Column(SmallInteger, default=0, comment="软删除标记")

    def __repr__(self):
        return f"<Order(id={self.id}, order_no='{self.order_no}', status='{self.status}')>"
