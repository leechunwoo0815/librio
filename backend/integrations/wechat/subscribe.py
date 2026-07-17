# backend/integrations/wechat/subscribe.py
"""微信订阅消息集成 — access_token 委托 WeChatService 统一管理"""

import asyncio
import logging

import httpx

from backend.common.exceptions import PaymentError, ValidationError
from backend.domain.wechat.service import WeChatService

logger = logging.getLogger(__name__)


class WeChatSubscribe:
    """微信订阅消息 — 替代已废弃的模板消息"""

    SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"

    @staticmethod
    async def send(openid: str, template_id: str, data: dict, page: str = "") -> dict:
        """
        发送订阅消息

        参数：
          openid: 用户 openid
          template_id: 模板 ID（在微信后台配置）
          data: 模板数据，格式 {"key1": {"value": "xxx"}, "key2": {"value": "yyy"}}
          page: 点击消息后跳转的小程序页面

        Raises:
            ValidationError: 参数错误（如模板 ID 无效）
            PaymentError: 微信接口返回系统错误
        """
        if not template_id:
            logger.warning("Subscribe message skipped: template_id is empty")
            return {"errcode": -1, "errmsg": "template_id not configured"}

        token_data = await _get_access_token()
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise PaymentError("获取微信 access_token 失败")

        body = {
            "touser": openid,
            "template_id": template_id,
            "data": data,
        }
        if page:
            body["page"] = page

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{WeChatSubscribe.SEND_URL}?access_token={access_token}",
                json=body,
            )
            result = resp.json()

        errcode = result.get("errcode", 0)
        if errcode != 0:
            errmsg = result.get("errmsg", "未知错误")
            if errcode in (40003, 41028, 41029, 41030):
                raise ValidationError(f"订阅消息发送失败: {errmsg}")
            elif errcode == 43101:
                # NOTE: openid 是公开标识，开发日志可记录全量；生产环境可按需脱敏。
                logger.info(f"User {openid} refused subscribe message")
                return result
            else:
                logger.error(
                    f"Subscribe message failed: errcode={errcode}, errmsg={errmsg}"
                )
                raise PaymentError(f"订阅消息发送失败: {errmsg}")

        return result


async def _get_access_token() -> dict:
    """获取微信 access_token — 委托 WeChatService 统一管理

    与 /wechat/qr-code 共享同一份带双重检查锁定的缓存，
    避免多套 token 管理机制并发刷新导致相互失效。
    """
    service = WeChatService()
    try:
        token = await asyncio.to_thread(service.get_access_token)
        return {"access_token": token}
    except Exception as e:
        logger.error(f"获取微信 access_token 失败: {e}")
        return {}
