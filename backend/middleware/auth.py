# backend/middleware/auth.py
"""
[What] JWT认证中间件
[Why] 保护需要登录的API
[How] 验证JWT Token，获取当前用户
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import get_settings
from backend.database import get_db
from backend.repositories.user_repo import UserRepository
from backend.schemas.user import UserResponse
import logging

logger = logging.getLogger(__name__)

settings = get_settings()
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    [What] 创建JWT Access Token
    [Why] 用户登录后需要生成Token
    [How] 使用python-jose编码JWT
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    [What] 验证JWT Token
    [Why] 解析Token获取用户信息
    [How] 使用python-jose解码JWT
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效或已过期",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db)
) -> UserResponse:
    """
    [What] 获取当前登录用户（依赖注入）
    [Why] 需要登录的API需要获取用户信息
    [How] 从Header中提取Token，验证并查询用户
    """
    token = credentials.credentials
    payload = verify_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token中缺少用户信息",
        )
    
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    
    return UserResponse.model_validate(user)
