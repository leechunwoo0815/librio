# backend/domain/user/router.py
"""用户域 API 路由 — 微信登录、手机号登录、用户管理"""

import logging

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_user_service
from backend.common.exceptions import ValidationError
from backend.middleware.auth import create_access_token, get_current_user
from backend.middleware.rate_limit import rate_limit
from backend.domain.user.schemas import (
    PhoneLoginRequest,
    SendSmsRequest,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    WxLoginResponse,
)
from backend.domain.user.service import UserService
from backend.integrations.wechat.auth import WeChatAuth

router = APIRouter(prefix="/user", tags=["用户"])

logger = logging.getLogger(__name__)


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
        raise ValidationError("微信登录失败，无法获取openid")

    user = user_service.find_or_create_by_openid(openid, wx_data.get("unionid"))

    phone = None
    if login_data.phone_code:
        phone = await WeChatAuth.get_phone_number(login_data.phone_code)
        if phone:
            user = user_service.update_user_phone(user.id, phone)

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


# ── 手机号+验证码登录（验证码通过短信网关发送）──


@router.post(
    "/send-sms",
    dependencies=[Depends(rate_limit(3, 60))],
)
async def send_sms(data: SendSmsRequest):
    """发送短信验证码"""
    from backend.common.dependencies import get_sms_gateway

    gateway = get_sms_gateway()
    result = await gateway.send_code(data.phone)
    if not result.success:
        raise ValidationError("验证码发送失败，请稍后重试")

    return {"message": "验证码已发送"}


@router.post(
    "/phone-login",
    response_model=WxLoginResponse,
    dependencies=[Depends(rate_limit(10, 60))],
)
async def phone_login(
    data: PhoneLoginRequest,
    user_service: UserService = Depends(get_user_service),
):
    """手机号+验证码登录

    1. 校验短信验证码（通过短信网关）
    2. 通过 wx.login code 获取 openid
    3. 根据 phone 查找用户，不存在则创建
    4. 返回 JWT token
    """
    # 1. 校验验证码（通过短信网关）
    from backend.common.dependencies import get_sms_gateway

    gateway = get_sms_gateway()
    if not await gateway.verify_code(data.phone, data.sms_code):
        raise ValidationError("验证码错误或已过期")

    # 2. 通过 code 获取 openid
    wx_data = await WeChatAuth.code_to_session(data.code)
    openid = wx_data.get("openid")
    if not openid:
        raise ValidationError("微信登录失败，无法获取openid")

    # 3. 根据 phone 查找或创建用户
    user = user_service.user_repo.get_by_phone(data.phone)
    if user:
        if not user.openid:
            user = user_service.link_openid(user.id, openid)
    else:
        user_data = UserCreate(openid=openid, phone=data.phone, unionid=wx_data.get("unionid"))
        created = user_service.create_user(user_data)
        user = user_service.user_repo.get_by_id(created.id)

    from backend.domain.user.schemas import UserResponse as UR
    user_response = UR.model_validate(user)

    token = create_access_token({"sub": str(user.id)})
    return WxLoginResponse(token=token, user=user_response)
