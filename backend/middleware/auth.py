# backend/middleware/auth.py
"""
[What] 认证中间件
[Why] 处理JWT认证和用户身份验证
[How] 使用FastAPI依赖注入实现
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.repositories.user_repo import UserRepository
from backend.schemas.user import UserResponse
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    [What] 获取当前认证用户
    [Why] 保护需要认证的API端点
    [How] 验证JWT token，返回用户信息
    """
    # TODO: 实现JWT验证逻辑
    # 临时实现：返回一个模拟用户
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证功能尚未实现",
        headers={"WWW-Authenticate": "Bearer"},
    )
