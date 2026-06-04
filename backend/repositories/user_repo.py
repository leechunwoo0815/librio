# backend/repositories/user_repo.py
"""
[What] 用户数据访问层
[Why] 封装数据库操作，与业务逻辑解耦
[How] 使用SQLAlchemy ORM查询
"""

from sqlalchemy.orm import Session
from backend.models.user import User
from typing import Optional


class UserRepository:
    """
    [What] 用户仓库类
    [Why] 封装用户相关的数据库操作
    [How] 注入数据库会话，执行CRUD操作
    """

    def __init__(self, db: Session):
        """
        [What] 初始化仓库
        [Why] 需要数据库会话
        [How] 注入db会话
        """
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        [What] 根据ID查询用户
        [Why] 获取用户详情
        [How] 使用SQLAlchemy查询
        """
        return self.db.query(User).filter(
            User.id == user_id,
            User.is_deleted == 0
        ).first()

    def get_by_phone(self, phone: str) -> Optional[User]:
        """
        [What] 根据手机号查询用户
        [Why] 检查手机号是否已注册
        [How] 使用SQLAlchemy查询
        """
        return self.db.query(User).filter(
            User.phone == phone,
            User.is_deleted == 0
        ).first()

    def get_by_openid(self, openid: str) -> Optional[User]:
        """
        [What] 根据openid查询用户
        [Why] 微信登录时查找用户
        [How] 使用SQLAlchemy查询
        """
        return self.db.query(User).filter(
            User.openid == openid,
            User.is_deleted == 0
        ).first()

    def create(self, user: User) -> User:
        """
        [What] 创建用户
        [Why] 注册新用户
        [How] 添加到数据库并提交
        """
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User) -> User:
        """
        [What] 更新用户
        [Why] 修改用户信息
        [How] 提交数据库更新
        """
        self.db.commit()
        self.db.refresh(user)
        return user
