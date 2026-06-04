# backend/services/user_service.py
"""
[What] 用户业务逻辑层
[Why] 封装用户相关的业务规则
[How] 调用仓库层，实现业务逻辑
"""

from backend.repositories.user_repo import UserRepository
from backend.schemas.user import UserCreate, UserResponse
from backend.models.user import User
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UserService:
    """
    [What] 用户服务类
    [Why] 封装用户业务逻辑
    [How] 注入仓库层，实现业务规则
    """

    def __init__(self, user_repo: UserRepository):
        """
        [What] 初始化服务
        [Why] 需要仓库层依赖
        [How] 注入user_repo
        """
        self.user_repo = user_repo

    def create_user(self, user_data: UserCreate) -> UserResponse:
        """
        [What] 创建用户
        [Why] 用户注册业务逻辑
        [How] 检查手机号唯一性，创建用户
        """
        logger.info(f"Creating user with phone: {user_data.phone}")

        # 检查手机号是否已注册
        existing_user = self.user_repo.get_by_phone(user_data.phone)
        if existing_user:
            logger.warning(f"Phone {user_data.phone} already registered")
            raise ValueError("手机号已注册")

        # 创建用户对象
        user = User(
            parent_name=user_data.parent_name,
            phone=user_data.phone,
            openid=user_data.openid,
            unionid=user_data.unionid,
            avatar=user_data.avatar,
        )

        # 保存到数据库
        created_user = self.user_repo.create(user)
        logger.info(f"User created successfully: {created_user.id}")

        return UserResponse.model_validate(created_user)

    def get_user_by_id(self, user_id: int) -> Optional[UserResponse]:
        """
        [What] 根据ID获取用户
        [Why] 查询用户详情
        [How] 调用仓库层查询
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None
        return UserResponse.model_validate(user)

    def get_user_by_openid(self, openid: str) -> Optional[UserResponse]:
        """
        [What] 根据openid获取用户
        [Why] 微信登录时查找用户
        [How] 调用仓库层查询
        """
        user = self.user_repo.get_by_openid(openid)
        if not user:
            return None
        return UserResponse.model_validate(user)
