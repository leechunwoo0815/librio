# backend/utils/wechat.py
"""
[What] 微信API工具类
[Why] 封装微信登录和支付接口
[How] 使用httpx异步请求微信API
"""

import hashlib
import logging
import time
import uuid

import httpx

from backend.config import get_settings
from backend.common.exceptions import ValidationError

logger = logging.getLogger(__name__)
settings = get_settings()

WECHAT_API_BASE = "https://api.weixin.qq.com"
WECHAT_PAY_BASE = "https://api.mch.weixin.qq.com"


async def code2session(code: str) -> dict[str, str]:
    """
    [What] 微信小程序登录
    [Why] 用临时code换取openid和session_key
    [How] GET https://api.weixin.qq.com/sns/jscode2session
    """
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        logger.warning("WeChat credentials not configured, using dev mode")
        return {"openid": f"dev_{code[:16]}", "session_key": "dev_session_key"}

    url = f"{WECHAT_API_BASE}/sns/jscode2session"
    params = {
        "appid": settings.WECHAT_APP_ID,
        "secret": settings.WECHAT_APP_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.error(f"WeChat API request failed: {e}")
        raise ValidationError("微信服务请求失败，请稍后重试")

    if "errcode" in data and data["errcode"] != 0:
        logger.error(f"WeChat login failed: {data}")
        raise ValidationError(f"微信登录失败: {data.get('errmsg', '未知错误')}")

    logger.info(f"WeChat login success: openid={data.get('openid', '?')[:8]}...")
    return {
        "openid": data["openid"],
        "session_key": data.get("session_key", ""),
        "unionid": data.get("unionid"),
    }


def generate_pay_params(
    openid: str, order_no: str, amount: float, description: str
) -> dict:
    """
    [What] 生成微信支付统一下单参数
    [Why] 小程序支付需要prepay_id
    [How] POST https://api.mch.weixin.qq.com/pay/unifiedorder (XML)
    """
    if not settings.WECHAT_APP_ID or not settings.WECHAT_MCH_ID:
        logger.warning("WeChat pay not configured, returning mock params")
        return {
            "prepay_id": f"prepay_mock_{order_no}",
            "package": "prepay_id=mock",
            "nonceStr": uuid.uuid4().hex[:16],
            "timeStamp": str(int(time.time())),
            "signType": "MD5",
            "paySign": "mock_sign",
        }

    params = {
        "appid": settings.WECHAT_APP_ID,
        "mch_id": settings.WECHAT_MCH_ID,
        "nonce_str": uuid.uuid4().hex[:16],
        "body": description,
        "out_trade_no": order_no,
        "total_fee": int(amount * 100),  # 金额：分
        "spbill_create_ip": "127.0.0.1",
        "notify_url": f"{settings.SERVER_HOST}:{settings.SERVER_PORT}/order/payment-callback"
        if settings.SERVER_HOST
        else "",
        "trade_type": "JSAPI",
        "openid": openid,
    }
    params["sign"] = _make_sign(params)
    return params


def verify_pay_callback(data: dict) -> bool:
    """
    [What] 验证微信支付回调签名
    [Why] 防止伪造回调
    [How] 用API密钥验证MD5签名
    """
    if not settings.WECHAT_API_KEY:
        logger.warning("WeChat API key not configured, skipping signature verification")
        return True

    sign = data.pop("sign", "")
    calculated = _make_sign(data)
    return sign == calculated


def _make_sign(params: dict) -> str:
    """
    [What] 生成微信支付签名
    [Why] 微信支付要求MD5签名
    [How] 按key排序→拼接→加key→MD5→大写
    """
    # 过滤空值和sign字段
    filtered = {k: v for k, v in params.items() if v and k != "sign"}
    # 按key排序
    sorted_items = sorted(filtered.items())
    # 拼接字符串
    sign_str = "&".join(f"{k}={v}" for k, v in sorted_items)
    sign_str += f"&key={settings.WECHAT_API_KEY}"
    # MD5并大写
    return hashlib.md5(sign_str.encode()).hexdigest().upper()
