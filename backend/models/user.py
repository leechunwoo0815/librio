# backend/models/user.py
"""
[What] 用户模型
[Why] 定义用户表结构
[How] 使用SQLAlchemy ORM映射
"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, SmallInteger, Integer
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    """
    [What] 用户模型类
    [Why] 映射到数据库的user表
    [How] 继承Base，定义表结构
    """
    __tablename__ = "user"
    
    # [What] 主键ID
    # [Why] 每条记录需要唯一标识
    # [How] 使用BigInteger自增主键（SQLite下使用Integer兼容）
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment="主键")
    
    # [What] 家长姓名
    # [Why] 记录用户基本信息
    # [How] 使用String，最多50字符
    parent_name = Column(String(50), nullable=True, comment="家长姓名")
    
    # [What] 手机号
    # [Why] 用户唯一标识，用于登录
    # [How] 使用String，唯一索引
    phone = Column(String(11), nullable=False, unique=True, index=True, comment="手机号")
    
    # [What] 密码
    # [Why] 管理端登录使用
    # [How] 使用bcrypt加密存储（比MD5更安全）
    password = Column(String(128), nullable=True, comment="密码（bcrypt加密）")
    
    # [What] 微信openid
    # [Why] 微信登录唯一标识
    # [How] 使用String，唯一索引
    openid = Column(String(100), nullable=False, unique=True, index=True, comment="微信openid")
    
    # [What] 微信unionid
    # [Why] 跨应用唯一标识
    # [How] 使用String
    unionid = Column(String(100), nullable=True, comment="微信unionid")
    
    # [What] 家长头像URL
    # [Why] 用户个性化展示
    # [How] 使用String存储URL
    avatar = Column(String(255), nullable=True, comment="家长头像URL")
    
    # [What] 当前选中的孩子ID
    # [Why] 多孩家庭需要切换当前孩子
    # [How] 使用BigInteger外键
    current_child_id = Column(BigInteger, nullable=True, index=True, comment="当前选中的孩子ID")
    
    # [What] 创建时间
    # [Why] 记录数据创建时间
    # [How] 使用DateTime，默认当前时间
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    # [What] 更新时间
    # [Why] 记录数据更新时间
    # [How] 使用DateTime，自动更新
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    
    # [What] 软删除标记
    # [Why] 逻辑删除，不物理删除数据
    # [How] 使用SmallInteger，0=未删除，1=已删除
    is_deleted = Column(SmallInteger, default=0, comment="软删除标记")
    
    # [What] 关联孩子表
    # [Why] 一个用户有多个孩子
    # [How] 使用relationship定义一对多关系
    children = relationship("Child", back_populates="user", foreign_keys="Child.user_id")
    
    def __repr__(self):
        return f"<User(id={self.id}, phone='{self.phone}', parent_name='{self.parent_name}')>"