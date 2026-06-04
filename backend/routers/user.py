# backend/routers/user.py
"""
[What] 用户API路由
[Why] 定义用户相关的API端点
[How] 使用FastAPI路由器
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.repositories.user_repo import UserRepository
from backend.services.user_service import UserService
from backend.schemas.user import UserCreate, UserResponse, UserLogin
from backend.middleware.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["用户"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """
    [What] 获取用户服务实例（依赖注入）
    [Why] FastAPI依赖注入模式
    [How] 创建仓库和服务实例
    """
    user_repo = UserRepository(db)
    return UserService(user_repo)


@router.post("/wx-login", response_model=UserResponse)
async def wx_login(login_data: UserLogin, user_service: UserService = Depends(get_user_service)):
    """
    [What] 微信登录接口
    [Why] 用户通过微信小程序登录
    [How] 调用微信API获取openid，查找或创建用户
    """
    # TODO: 调用微信API获取openid
    # openid = await wechat.get_openid(login_data.code)

    # 临时实现：使用code作为openid
    openid = login_data.code

    # 查找或创建用户
    user = user_service.get_user_by_openid(openid)
    if not user:
        # 自动创建用户
        user_data = UserCreate(openid=openid, phone="00000000000")
        user = user_service.create_user(user_data)

    return user


@router.get("/info", response_model=UserResponse)
async def get_user_info(current_user: UserResponse = Depends(get_current_user)):
    """
    [What] 获取当前用户信息
    [Why] 前端需要用户信息
    [How] 从JWT中获取用户ID，查询用户
    """
    return current_user
