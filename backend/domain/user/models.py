# backend/domain/user/models.py
"""用户域模型 — 微信登录、JWT 认证"""

from sqlalchemy import BigInteger, Column, Integer, SmallInteger, String
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel


class User(BaseModel):
    """用户模型 — 家长"""

    __tablename__ = "user"
    __table_args__ = {"extend_existing": True}

    STATUS_ACTIVE = 1
    STATUS_DISABLED = 0

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
    status = Column(
        SmallInteger,
        nullable=False,
        default=STATUS_ACTIVE,
        server_default="1",
        comment="1=启用 0=禁用",
    )
    token_generation = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Token版本号，改密码/禁用时+1使旧Token失效",
    )

    children = relationship(
        "Child", back_populates="user", foreign_keys="Child.user_id"
    )

    def __repr__(self):
        return f"<User(id={self.id}, phone='{self.phone}', parent_name='{self.parent_name}')>"
