# backend/domain/user/router.py
"""用户域 API 路由 — 微信登录、用户管理"""

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_user_service
from backend.middleware.auth import create_access_token, get_current_user
from backend.middleware.rate_limit import rate_limit
from backend.domain.user.schemas import (
    UserLogin,
    UserResponse,
    UserUpdate,
    WxLoginResponse,
)
from backend.domain.user.service import UserService
from backend.integrations.wechat.auth import WeChatAuth

router = APIRouter(prefix="/user", tags=["用户"])


@router.post(
    "/wx-login",
    response_model=WxLoginResponse,
    dependencies=[Depends(rate_limit(10, 60))],
)
async def wx_login(
    login_data: UserLogin,
    user_service: UserService = Depends(get_user_service),
):
    """微信登录 — code2session 获取 openid，查找或创建用户"""
    wx_data = await WeChatAuth.code_to_session(login_data.code)
    openid = wx_data.get("openid")
    if not openid:
        from backend.common.exceptions import ValidationError

        raise ValidationError("微信登录失败，无法获取openid")

    user = user_service.find_or_create_by_openid(openid, wx_data.get("unionid"))

    token = create_access_token({"sub": str(user.id)})
    return WxLoginResponse(token=token, user=user)


@router.get("/info", response_model=UserResponse)
def get_user_info(current_user=Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.put("/info", response_model=UserResponse)
def update_user_info(
    update_data: UserUpdate,
    user_service: UserService = Depends(get_user_service),
    current_user=Depends(get_current_user),
):
    """更新当前用户信息"""
    return user_service.update_user(current_user.id, update_data)
