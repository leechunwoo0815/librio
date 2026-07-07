# backend/middleware/auth.py
"""
[What] JWT认证中间件
[Why] 保护需要登录的API
[How] 验证JWT Token，获取当前用户
"""

import logging
import uuid
from datetime import datetime, timedelta

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.common.exceptions import UnauthorizedError
from backend.config import get_settings
from backend.database import get_db
from backend.domain.user.repository import UserRepository
from backend.domain.user.schemas import UserResponse

logger = logging.getLogger(__name__)

settings = get_settings()
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    [What] 创建JWT Access Token
    [Why] 用户登录后需要生成Token
    [How] 使用python-jose编码JWT
    """
    to_encode = data.copy()
    from datetime import timezone

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update(
        {"exp": expire, "iat": datetime.now(timezone.utc), "jti": str(uuid.uuid4())}
    )
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    [What] 验证JWT Token
    [Why] 解析Token获取用户信息
    [How] 使用python-jose解码JWT
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.error(f"Token verification failed: {e}")
        raise UnauthorizedError("Token无效或已过期")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db=Depends(get_db)
) -> UserResponse:
    """
    [What] 获取当前登录用户（依赖注入）
    [Why] 需要登录的API需要获取用户信息
    [How] 从Header中提取Token，验证并查询用户
    """
    token = credentials.credentials

    # 仅在 DEBUG 模式下允许测试 token（生产环境绝不生效）
    if settings.DEBUG and token == "test-token-mock":
        logger.warning("Using test-token-mock in DEBUG mode")
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(1)
        if user:
            return UserResponse.model_validate(user)

    payload = verify_token(token)
    if payload.get("type") == "admin":
        # 管理员 token 不应访问用户 API
        # 管理后台应使用 /admin/api/* 专用端点
        raise UnauthorizedError("管理员Token不能访问用户API，请使用管理端专用接口")
    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Token中缺少用户信息")

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(int(user_id))
    if user is None:
        raise UnauthorizedError("用户不存在")

    return UserResponse.model_validate(user)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
    db=Depends(get_db),
) -> UserResponse | None:
    """可选认证：DEBUG 模式下无 token 返回 None，生产环境必须有 token。"""
    if credentials is None:
        if settings.DEBUG:
            return None
        raise UnauthorizedError("缺少认证信息")

    token = credentials.credentials
    if settings.DEBUG and token == "test-token-mock":
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(1)
        if user:
            return UserResponse.model_validate(user)

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        if settings.DEBUG:
            return None
        raise UnauthorizedError("Token无效")

    user_id = payload.get("sub")
    if user_id is None:
        return None

    if payload.get("type") == "admin":
        raise UnauthorizedError("Token类型不匹配，请使用用户token")

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(int(user_id))
    return UserResponse.model_validate(user) if user else None
