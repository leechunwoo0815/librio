# backend/common/gateways/exceptions.py
"""统一网关异常体系 — 对齐现有 backend/common/exceptions.py"""


class GatewayException(Exception):
    """网关层统一异常基类"""


class PaymentException(GatewayException):
    """支付网关异常"""


class PaymentSignatureException(PaymentException):
    """支付签名验证失败"""


class PaymentRefundException(PaymentException):
    """退款操作失败"""


class SmsException(GatewayException):
    """短信网关异常"""


class SmsSendException(SmsException):
    """短信发送失败"""


class SmsVerifyException(SmsException):
    """验证码校验失败"""
