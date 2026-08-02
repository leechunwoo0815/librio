"""WeChat API service — access_token caching, QR code generation"""

import logging
import threading
import time
from typing import Optional

import httpx
from backend.config import get_settings

logger = logging.getLogger(__name__)

WECHAT_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WECHAT_QR_URL = "https://api.weixin.qq.com/wxa/getwxacodeunlimit"
CACHE_TTL = 7000


class WeChatAPIError(Exception):
    """WeChat API 调用失败"""


class _AccessTokenCache:
    """access_token 缓存：Redis 为主（多实例共享，审查 P2-3），进程内存为降级。

    多实例部署时若各进程独立刷新 token，微信侧会使旧 token 互踢失效，
    导致刷新风暴甚至触发频率限制。Redis 共享后全集群只刷新一次。
    """

    REDIS_KEY = "wechat:access_token"

    def __init__(self):
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires_at: float = 0

    def get(self) -> Optional[str]:
        # 最快路径：进程内缓存
        if self._token and time.time() < self._expires_at:
            return self._token
        # 其次：Redis 共享缓存（其他实例可能已刷新）
        try:
            from backend.common.distributed_lock import get_redis_client

            data = get_redis_client().get(self.REDIS_KEY)
            if data:
                token, expires_at = data.rsplit("|", 1)
                if time.time() < float(expires_at):
                    self._token, self._expires_at = token, float(expires_at)
                    return token
        except Exception:
            pass  # Redis 不可用静默降级为进程内缓存
        return None

    def set(self, token: str, expires_in: int):
        expires_at = time.time() + min(expires_in, CACHE_TTL)
        with self._lock:
            self._token = token
            self._expires_at = expires_at
        try:
            from backend.common.distributed_lock import get_redis_client

            ttl = int(expires_at - time.time())
            if ttl > 0:
                get_redis_client().set(self.REDIS_KEY, f"{token}|{expires_at}", ex=ttl)
        except Exception:
            pass  # Redis 写失败不影响进程内缓存


_token_cache = _AccessTokenCache()
_token_refresh_lock = threading.Lock()


class WeChatService:
    """微信服务：access_token管理 + 小程序码生成

    所有方法均为同步，QR 码端点在 Router 层使用 asyncio.to_thread 异步调用。
    access_token 使用双重检查锁定防并发击穿。
    """

    def __init__(self):
        settings = get_settings()
        self.app_id = settings.WECHAT_APP_ID
        self.app_secret = settings.WECHAT_APP_SECRET

    def get_access_token(self) -> str:
        """获取缓存的access_token，双重检查锁定防并发击穿"""
        cached = _token_cache.get()
        if cached:
            return cached

        with _token_refresh_lock:
            cached = _token_cache.get()
            if cached:
                return cached

            return self._fetch_access_token()

    def _fetch_access_token(self) -> str:
        """从微信API获取新access_token"""
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }
        resp = httpx.get(WECHAT_TOKEN_URL, params=params, timeout=10)
        data = resp.json()
        if "access_token" not in data:
            raise WeChatAPIError(
                f"获取access_token失败: {data.get('errmsg', '未知错误')}"
            )
        token = data["access_token"]
        expires_in = data.get("expires_in", 7200)
        _token_cache.set(token, expires_in)
        logger.info("WeChat access_token refreshed (expires_in=%ds)", expires_in)
        return token

    def get_unlimited_qr_code(self, scene: str, page: str) -> bytes:
        """生成微信小程序码（无数量限制）

        Args:
            scene: 场景值（如 cert_123, report_456_week）
            page: 小程序页面路径

        Returns:
            PNG 图片字节流

        Raises:
            WeChatAPIError: 微信接口调用失败
        """
        token = self.get_access_token()
        url = f"{WECHAT_QR_URL}?access_token={token}"
        payload = {
            "scene": scene,
            "page": page,
            "check_path": True,
            "env_version": "release",
            "width": 280,
        }
        resp = httpx.post(url, json=payload, timeout=15)

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            data = resp.json()
            raise WeChatAPIError(f"生成小程序码失败: {data.get('errmsg', '未知错误')}")

        return resp.content
