# backend/integrations/wechat/pay_v3.py
"""微信支付 V3 版本 — JSON + SHA256-RSA 签名

替换旧的 V2 XML + MD5 签名协议。

V3 优势：
  1. RSA 非对称签名，比 MD5 更安全
  2. 回调通知有加密和签名
  3. 支持合单支付、服务商模式等更多能力
  4. 微信官方已推荐 V3，V2 进入维护模式

安全要求：
  - 金额必须用整数分，禁止浮点数
  - 回调验签必须使用平台证书，禁止跳过
  - 商户私钥必须安全存储

新增配置项（需在 .env 中添加）：
  WECHAT_API_KEY_V3 — V3 专用 API 密钥（32 字节）
  WECHAT_CERT_SERIAL_NO — 商户证书序列号
  WECHAT_PRIVATE_KEY_PATH — 商户私钥 PEM 文件路径
  WECHAT_PLATFORM_CERT_PATH — 微信平台证书 PEM 文件路径
  WECHAT_PAY_NOTIFY_URL — 支付回调通知 URL
"""

import base64
import json
import logging
import time
import uuid
from pathlib import Path

import httpx

# cryptography 是运行时依赖，生产环境部署时需安装
# 开发环境下若未安装，类实例化时会报错，但不影响模块导入
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidSignature
    from cryptography.x509 import load_pem_x509_certificate

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

from backend.config import get_settings
from backend.common.exceptions import PaymentError

logger = logging.getLogger(__name__)


class WeChatPayV3:
    """微信支付 V3 — SHA256-RSA 签名"""

    BASE_URL = "https://api.mch.weixin.qq.com"

    def __init__(self):
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError(
                "cryptography 包未安装。请运行: pip install cryptography\n"
                "微信支付 V3 需要 cryptography 进行 RSA 签名和 AES-GCM 解密。"
            )

        settings = get_settings()
        self.appid = settings.WECHAT_APP_ID
        self.mchid = settings.WECHAT_MCH_ID
        self.api_key_v3 = getattr(settings, "WECHAT_API_KEY_V3", "")
        self.serial_no = getattr(settings, "WECHAT_CERT_SERIAL_NO", "")

        # 加载商户私钥
        key_path = Path(getattr(settings, "WECHAT_PRIVATE_KEY_PATH", ""))
        if key_path.exists():
            self.private_key = serialization.load_pem_private_key(
                key_path.read_bytes(), password=None
            )
        else:
            self.private_key = None

        # 加载微信平台证书（用于验签）
        # TODO: 生产环境应实现自动轮换 — 定期调用 /v3/certificates API 获取最新平台证书
        # 微信平台证书有效期约 1 年，到期后验签全部失败
        cert_path = Path(getattr(settings, "WECHAT_PLATFORM_CERT_PATH", ""))
        if cert_path.exists():
            self.platform_cert = load_pem_x509_certificate(cert_path.read_bytes())
        else:
            self.platform_cert = None

    def _sign(self, message: str) -> str:
        """SHA256-RSA 签名"""
        if not self.private_key:
            raise RuntimeError("商户私钥未配置，无法签名")
        signature = self.private_key.sign(
            message.encode(), padding.PKCS1v15(), hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    def _build_auth_header(self, method: str, url: str, body: str = "") -> str:
        """构建 Authorization 请求头"""
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        sign_message = f"{method}\n{url}\n{timestamp}\n{nonce}\n{body}\n"
        signature = self._sign(sign_message)
        return (
            f"WECHATPAY2-SHA256-RSA2048 "
            f'mchid="{self.mchid}",nonce_str="{nonce}",'
            f'timestamp="{timestamp}",serial_no="{self.serial_no}",'
            f'signature="{signature}"'
        )

    async def create_jsapi_order(
        self, openid: str, order_no: str, amount_cent: int, description: str
    ) -> dict:
        """
        JSAPI 下单（小程序支付）

        参数：
          openid: 用户微信 openid
          order_no: 商户订单号
          amount_cent: 金额（分），整数，避免浮点精度问题
          description: 商品描述

        返回：
          wx.requestPayment 所需参数
        """
        url = "/v3/pay/transactions/jsapi"
        body = {
            "appid": self.appid,
            "mchid": self.mchid,
            "description": description,
            "out_trade_no": order_no,
            "notify_url": getattr(get_settings(), "WECHAT_PAY_NOTIFY_URL", ""),
            "amount": {"total": amount_cent, "currency": "CNY"},
            "payer": {"openid": openid},
        }
        body_str = json.dumps(body, ensure_ascii=False)

        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=10) as client:
            resp = await client.post(
                url,
                content=body_str,
                headers={
                    "Authorization": self._build_auth_header("POST", url, body_str),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

        if resp.status_code not in (200, 202):
            try:
                error_msg = resp.json().get("message", "未知错误")
            except Exception:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            raise PaymentError(f"微信下单失败: {error_msg}")

        data = resp.json()

        prepay_id = data["prepay_id"]
        return self._build_miniapp_pay_params(prepay_id)

    def _build_miniapp_pay_params(self, prepay_id: str) -> dict:
        """生成 wx.requestPayment 所需参数"""
        timestamp = str(int(time.time()))
        nonce_str = uuid.uuid4().hex
        package = f"prepay_id={prepay_id}"
        sign_message = f"{self.appid}\n{timestamp}\n{nonce_str}\n{package}\n"
        pay_sign = self._sign(sign_message)

        return {
            "timeStamp": timestamp,
            "nonceStr": nonce_str,
            "package": package,
            "signType": "RSA",
            "paySign": pay_sign,
        }

    def verify_callback(self, headers: dict, body: str) -> dict | None:
        """
        验证支付回调签名并解密

        返回：解密后的通知内容，验签失败返回 None
        """
        if not self.platform_cert:
            raise RuntimeError("微信平台证书未配置，无法验签")

        # 1. 验证签名
        signature_b64 = headers.get("wechatpay-signature", "")
        timestamp = headers.get("wechatpay-timestamp", "")
        nonce = headers.get("wechatpay-nonce", "")
        sign_message = f"{timestamp}\n{nonce}\n{body}\n"

        try:
            self.platform_cert.public_key().verify(
                base64.b64decode(signature_b64),
                sign_message.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature:
            return None
        except Exception:
            raise

        # 2. 解密通知内容
        encrypted = json.loads(body).get("resource", {})
        nonce_bytes = encrypted["nonce"].encode()
        associated_data = encrypted.get("associated_data", "").encode()
        ciphertext = base64.b64decode(encrypted["ciphertext"])

        aes_key = self.api_key_v3.encode()
        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(nonce_bytes, ciphertext, associated_data)
        return json.loads(plaintext)

    async def query_order(self, out_trade_no: str) -> dict:
        """查询订单"""
        url = f"/v3/pay/transactions/out-trade-no/{out_trade_no}"
        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=10) as client:
            resp = await client.get(
                url,
                headers={
                    "Authorization": self._build_auth_header("GET", url),
                    "Accept": "application/json",
                },
            )
        if resp.status_code != 200:
            try:
                error_msg = resp.json().get("message", "未知错误")
            except Exception:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            raise PaymentError(f"微信查询订单失败: {error_msg}")
        return resp.json()

    async def refund(
        self,
        out_trade_no: str,
        out_refund_no: str,
        total_cent: int,
        refund_cent: int,
        reason: str = "",
    ) -> dict:
        """申请退款"""
        url = "/v3/refund/domestic/refunds"
        body = {
            "out_trade_no": out_trade_no,
            "out_refund_no": out_refund_no,
            "amount": {"refund": refund_cent, "total": total_cent, "currency": "CNY"},
            "reason": reason or "用户申请退款",
        }
        body_str = json.dumps(body, ensure_ascii=False)

        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=10) as client:
            resp = await client.post(
                url,
                content=body_str,
                headers={
                    "Authorization": self._build_auth_header("POST", url, body_str),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        if resp.status_code not in (200, 202):
            try:
                error_msg = resp.json().get("message", "未知错误")
            except Exception:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            raise PaymentError(f"微信退款申请失败: {error_msg}")
        return resp.json()

    async def refresh_platform_cert(self) -> bool:
        """从微信 API 下载最新平台证书

        微信平台证书有效期约 1 年，建议每周自动刷新一次。
        返回：True 表示成功更新，False 表示未更新或失败
        """
        if not self.private_key:
            logger.warning("Cannot refresh platform cert: private key not configured")
            return False

        url = "/v3/certificates"
        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=10) as client:
            resp = await client.get(
                url,
                headers={
                    "Authorization": self._build_auth_header("GET", url),
                    "Accept": "application/json",
                },
            )

        if resp.status_code != 200:
            logger.error(f"Failed to fetch platform certs: HTTP {resp.status_code}")
            return False

        data = resp.json()
        for cert_info in data.get("data", []):
            encrypted_cert = cert_info.get("encrypt_certificate", {})
            try:
                nonce = encrypted_cert["nonce"].encode()
                associated_data = encrypted_cert.get("associated_data", "").encode()
                ciphertext = base64.b64decode(encrypted_cert["ciphertext"])
                aesgcm = AESGCM(self.api_key_v3.encode())
                cert_pem = aesgcm.decrypt(nonce, ciphertext, associated_data)

                from cryptography.x509 import load_pem_x509_certificate

                new_cert = load_pem_x509_certificate(cert_pem)

                if (
                    self.platform_cert
                    and new_cert.not_valid_after <= self.platform_cert.not_valid_after
                ):
                    continue

                cert_path = Path(get_settings().WECHAT_PLATFORM_CERT_PATH)
                if cert_path.parent.exists():
                    cert_path.write_bytes(cert_pem)
                self.platform_cert = new_cert
                logger.info(
                    f"Platform cert refreshed, valid until: {new_cert.not_valid_after}"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to decrypt platform cert: {e}")
                continue

        return False
