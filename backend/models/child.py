# backend/models/child.py
"""
[What] 孩子模型
[Why] 定义孩子表结构
[How] 使用SQLAlchemy ORM映射
"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, SmallInteger, Numeric, ForeignKey, Integer
from sqlalchemy.orm import relationship
from backend.database import Base


class Child(Base):
    """
    [What] 孩子模型类
    [Why] 映射到数据库的child表
    [How] 继承Base，定义表结构
    """
    __tablename__ = "child"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(BigInteger, ForeignKey("user.id"), nullable=False, index=True, comment="关联用户表ID")
    name = Column(String(50), nullable=False, comment="孩子姓名")
    age = Column(SmallInteger, nullable=False, comment="孩子年龄")
    grade = Column(String(20), nullable=False, comment="孩子年级")
    
    # [What] 会员状态
    # [Why] 记录孩子的会员等级
    # [How] 使用SmallInteger枚举：0=体验用户，1=观察期，2=正式会员，3=已过期，4=已退出
    status = Column(SmallInteger, default=0, comment="会员状态")
    
    member_start_time = Column(DateTime, nullable=True, comment="会员开始时间")
    member_expire_time = Column(DateTime, nullable=True, comment="会员到期时间")
    ar_level = Column(Numeric(3, 1), nullable=True, comment="AR阅读等级")
    
    # [What] 押金状态
    # [Why] 记录押金支付情况
    # [How] 使用SmallInteger枚举：0=未支付，1=已支付，2=已退还
    deposit_status = Column(SmallInteger, default=0, comment="押金状态")
    deposit_amount = Column(Numeric(10, 2), nullable=True, comment="押金金额")
    
    teacher_id = Column(BigInteger, nullable=True, comment="分配的老师ID")
    venue_id = Column(BigInteger, nullable=True, comment="所属场馆ID")
    
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    is_deleted = Column(SmallInteger, default=0, comment="软删除标记")
    
    # [What] 关联用户表
    # [Why] 孩子属于某个用户
    # [How] 使用relationship定义多对一关系
    user = relationship("User", back_populates="children", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<Child(id={self.id}, name='{self.name}', status={self.status})>"