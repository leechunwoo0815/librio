# backend/domain/user/service.py
"""用户域业务逻辑 — 微信登录、用户管理"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.common.exceptions import ConflictError
from backend.domain.user.models import User
from backend.domain.user.repository import UserRepository
from backend.domain.user.schemas import UserCreate, UserResponse, UserUpdate

logger = logging.getLogger(__name__)


class UserService:
    """用户服务

    架构意图：
      - 构造函数只接收 db: Session，内部自行构造 Repository
      - 抛 BusinessException 体系，不抛 ValueError
      - 事务边界在 Service 层：调用 db.commit()
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def create_user(self, user_data: UserCreate) -> UserResponse:
        """创建用户 — 支持微信登录（无需手机号）和手机号注册"""
        logger.info(f"Creating user with openid: {user_data.openid}")

        # 手机号唯一性检查
        if user_data.phone:
            existing = self.user_repo.get_by_phone(user_data.phone)
            if existing:
                raise ConflictError("手机号已注册")

        user = User(
            parent_name=user_data.parent_name,
            phone=user_data.phone,
            openid=user_data.openid,
            unionid=user_data.unionid,
            avatar=user_data.avatar,
        )

        created = self.user_repo.create(user)
        self.db.commit()
        logger.info(f"User created: id={created.id}")
        return UserResponse.model_validate(created)

    def get_user_by_id(self, user_id: int) -> UserResponse:
        """根据 ID 获取用户，不存在则抛 NotFoundError"""
        user = self.user_repo.get_by_id_or_raise(user_id)
        return UserResponse.model_validate(user)

    def get_user_by_openid(self, openid: str) -> Optional[UserResponse]:
        """根据 openid 获取用户（微信登录）"""
        user = self.user_repo.get_by_openid(openid)
        if not user:
            return None
        return UserResponse.model_validate(user)

    def find_or_create_by_openid(
        self, openid: str, unionid: str | None = None
    ) -> UserResponse:
        """根据 openid 查找或创建用户 — 微信登录核心流程"""
        user = self.user_repo.get_by_openid(openid)
        if user:
            return UserResponse.model_validate(user)

        # 新用户
        user_data = UserCreate(openid=openid, unionid=unionid)
        return self.create_user(user_data)

    def update_user(self, user_id: int, update_data: UserUpdate) -> UserResponse:
        """更新用户信息"""
        user = self.user_repo.get_by_id_or_raise(user_id)

        if update_data.phone is not None:
            # 手机号唯一性检查（排除自身）
            existing = self.user_repo.get_by_phone(update_data.phone)
            if existing and existing.id != user_id:
                raise ConflictError("手机号已被其他用户使用")
            user.phone = update_data.phone

        if update_data.parent_name is not None:
            user.parent_name = update_data.parent_name
        if update_data.avatar is not None:
            user.avatar = update_data.avatar

        self.user_repo.update(user)
        self.db.commit()
        return UserResponse.model_validate(user)

    def set_current_child(self, user_id: int, child_id: int) -> UserResponse:
        """设置当前选中的孩子"""
        user = self.user_repo.get_by_id_or_raise(user_id)
        user.current_child_id = child_id
        self.user_repo.update(user)
        self.db.commit()
        return UserResponse.model_validate(user)
