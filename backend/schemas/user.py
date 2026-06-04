# backend/schemas/user.py
"""
[What] 用户Pydantic模型
[Why] 用于API请求/响应数据验证
[How] 使用Pydantic定义数据结构
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    """
    [What] 创建用户请求模型
    [Why] 验证创建用户的数据格式
    [How] 定义必填和可选字段
    """
    parent_name: Optional[str] = Field(None, max_length=50, description="家长姓名")
    phone: str = Field(..., min_length=11, max_length=11, description="手机号")
    openid: str = Field(..., description="微信openid")
    unionid: Optional[str] = Field(None, description="微信unionid")
    avatar: Optional[str] = Field(None, description="头像URL")


class UserResponse(BaseModel):
    """
    [What] 用户响应模型
    [Why] API返回用户信息
    [How] 定义返回字段
    """
    id: int
    parent_name: Optional[str]
    phone: str
    openid: str
    current_child_id: Optional[int]
    create_time: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """
    [What] 用户登录请求模型
    [Why] 微信登录需要code
    [How] 定义code字段
    """
    code: str = Field(..., description="微信登录code")
