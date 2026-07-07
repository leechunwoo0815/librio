# backend/domain/user/models.py
"""用户域模型 — 微信登录、JWT 认证"""

from sqlalchemy import BigInteger, Column, String
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel


class User(BaseModel):
    """用户模型 — 家长"""

    __tablename__ = "user"
    __table_args__ = {"extend_existing": True}

    parent_name = Column(String(50), nullable=True, comment="家长姓名")
    phone = Column(String(11), nullable=True, unique=True, index=True, comment="手机号")
    password = Column(String(128), nullable=True, comment="密码（bcrypt加密）")
    openid = Column(
        String(100), nullable=False, unique=True, index=True, comment="微信openid"
    )
    unionid = Column(String(100), nullable=True, comment="微信unionid")
    avatar = Column(String(255), nullable=True, comment="家长头像URL")
    current_child_id = Column(
        BigInteger, nullable=True, index=True, comment="当前选中的孩子ID"
    )

    children = relationship(
        "Child", back_populates="user", foreign_keys="Child.user_id"
    )

    def __repr__(self):
        return f"<User(id={self.id}, phone='{self.phone}', parent_name='{self.parent_name}')>"
