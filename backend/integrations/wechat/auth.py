# backend/integrations/wechat/auth.py
"""微信登录集成 — 统一使用 BusinessException"""

import httpx

from backend.config import get_settings
from backend.common.exceptions import ValidationError, ForbiddenError


class WeChatAuth:
    """微信登录 — code 换 openid"""

    CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"

    @staticmethod
    async def code_to_session(code: str) -> dict:
        """用 code 换取 openid 和 session_key

        Raises:
            ValidationError: code 无效或过期
            ForbiddenError: 微信接口返回权限错误
        """
        settings = get_settings()
        params = {
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(WeChatAuth.CODE2SESSION_URL, params=params)
            data = resp.json()

        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "未知错误")
            if errcode in (40029, 40163):
                # code 无效或已使用
                raise ValidationError(f"微信登录失败: code无效或已过期 ({errmsg})")
            elif errcode in (40013, 40125):
                # appid/secret 配置错误
                raise ForbiddenError(f"微信登录配置错误: {errmsg}")
            else:
                raise ValidationError(f"微信登录失败: {errmsg}")

        return data
