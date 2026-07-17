# backend/domain/user/schemas.py
"""用户域 Pydantic 模型 — 请求/响应数据验证"""

from datetime import datetime

from pydantic import Field

from backend.common.base_schema import BaseSchema


class UserCreate(BaseSchema):
    """创建用户请求"""

    parent_name: str | None = Field(None, max_length=50, description="家长姓名")
    phone: str | None = Field(
        None, min_length=11, max_length=11, description="手机号（可选）"
    )
    openid: str = Field(..., description="微信openid")
    unionid: str | None = Field(None, description="微信unionid")
    avatar: str | None = Field(None, description="头像URL")


class UserResponse(BaseSchema):
    """用户响应"""

    id: int
    parent_name: str | None = None
    phone: str | None = None
    avatar: str | None = None
    current_child_id: int | None = None
    create_time: datetime


class UserUpdate(BaseSchema):
    """更新用户请求"""

    parent_name: str | None = Field(None, max_length=50, description="家长姓名")
    phone: str | None = Field(None, min_length=11, max_length=11, description="手机号")
    avatar: str | None = Field(None, description="头像URL")


class UserLogin(BaseSchema):
    """微信登录请求"""

    code: str = Field(..., description="微信登录code")
    phone_code: str | None = Field(None, description="微信手机号临时code（getPhoneNumber 返回）")


class PhoneLoginRequest(BaseSchema):
    """手机号+验证码登录请求"""

    code: str = Field(..., description="微信登录code（用于获取openid）")
    phone: str = Field(..., min_length=11, max_length=11, description="手机号")
    sms_code: str = Field(..., min_length=4, max_length=6, description="短信验证码")


class SendSmsRequest(BaseSchema):
    """发送短信验证码请求"""

    phone: str = Field(..., min_length=11, max_length=11, description="手机号")


class WxLoginResponse(BaseSchema):
    """微信登录响应"""

    token: str = Field(..., description="JWT token")
    user: UserResponse
