# backend/integrations/wechat/subscribe.py
"""微信订阅消息集成 — 带 Redis/内存双层缓存 + 错误码处理"""

import time
import logging

import httpx

from backend.config import get_settings
from backend.common.exceptions import PaymentError, ValidationError

logger = logging.getLogger(__name__)


# ============================================================
# Redis 客户端（带连接容错）
# ============================================================

_redis_client = None
_redis_checked = False


def _get_redis():
    """获取 Redis 客户端，不可用时返回 None"""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    try:
        import redis as redis_lib

        _redis_client = redis_lib.from_url(
            get_settings().REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
        _redis_client.ping()
        logger.info("Redis connected for access_token cache")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable, falling back to memory cache: {e}")
        _redis_client = None
        return None


# 内存缓存（Redis 不可用时的降级）
_token_cache: dict = {
    "access_token": "",
    "expires_at": 0,
}


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
                logger.info(f"User {openid} refused subscribe message")
                return result
            else:
                logger.error(
                    f"Subscribe message failed: errcode={errcode}, errmsg={errmsg}"
                )
                raise PaymentError(f"订阅消息发送失败: {errmsg}")

        return result


async def _get_access_token() -> dict:
    """获取微信 access_token（Redis 优先，内存降级）

    access_token 有效期 2 小时，提前 5 分钟刷新。
    """
    now = time.time()

    # 优先从 Redis 读取
    redis_client = _get_redis()
    if redis_client:
        try:
            cached = redis_client.get("wechat:access_token")
            if cached:
                return {"access_token": cached.decode()}
        except Exception as e:
            logger.warning(f"Redis read failed, falling back to memory: {e}")

    # 内存缓存检查
    if _token_cache["access_token"] and _token_cache["expires_at"] > now:
        return _token_cache

    # 请求微信 API
    settings = get_settings()
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": settings.WECHAT_APP_ID,
        "secret": settings.WECHAT_APP_SECRET,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "access_token" in data:
        token = data["access_token"]
        expires_in = data.get("expires_in", 7200)
        ttl = expires_in - 300  # 提前 5 分钟过期

        # 写入 Redis
        if redis_client:
            try:
                redis_client.setex("wechat:access_token", ttl, token)
            except Exception as e:
                logger.warning(f"Redis write failed: {e}")

        # 写入内存缓存
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = now + ttl
        logger.info("WeChat access_token refreshed")
    else:
        logger.error(f"Failed to get access_token: {data}")

    return data
