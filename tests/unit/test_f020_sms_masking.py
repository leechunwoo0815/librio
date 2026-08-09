# tests/unit/test_f020_sms_masking.py
"""F-020 终审闭环：SMS 网关 dev 模式日志 phone 脱敏回归测试

根因（复审 P2）：tencent.py send_notification dev 分支（SDK/凭据未配置时触发）
日志明文 request.phone——同位置 aliyun.py 已脱敏，tencent 漏改（同类漏改模式 1）。
本测试守护 tencent/aliyun 两处 dev 分支 + 非 dev 成功分支日志均不出现完整手机号。
"""

import asyncio
import logging

from backend.common.gateways.sms.types import SmsSendRequest
from backend.integrations.sms import aliyun, tencent

PHONE = "13800000001"
MASKED = "138****0001"


def _run(coro):
    return asyncio.run(coro)


class TestF020SmsDevLogMasking:
    def test_tencent_dev_notification_masks_phone(self, monkeypatch, caplog):
        """tencent dev 分支（SDK 未配置）：通知日志必须脱敏（本次修复点）"""
        monkeypatch.setattr(tencent, "_HAS_SDK", False)
        gw = tencent.TencentSmsGateway(
            app_id="", app_key="", sign_name="x", template_code="x"
        )
        with caplog.at_level(logging.INFO, logger="backend.integrations.sms.tencent"):
            resp = _run(
                gw.send_notification(SmsSendRequest(phone=PHONE, template_id="1"))
            )
        assert resp.success is True
        assert MASKED in caplog.text
        assert PHONE not in caplog.text, (
            f"tencent dev 日志泄露完整手机号: {caplog.text}"
        )

    def test_tencent_dev_send_code_masks_phone(self, monkeypatch, caplog):
        """tencent dev 分支验证码路径脱敏（防回归）"""
        monkeypatch.setattr(tencent, "_HAS_SDK", False)
        gw = tencent.TencentSmsGateway(
            app_id="", app_key="", sign_name="x", template_code="x"
        )
        with caplog.at_level(logging.INFO, logger="backend.integrations.sms.tencent"):
            resp = _run(gw.send_code(PHONE))
        assert resp.success is True
        assert PHONE not in caplog.text

    def test_aliyun_dev_notification_masks_phone(self, monkeypatch, caplog):
        """aliyun dev 分支对照（防同类漏改再犯）"""
        monkeypatch.setattr(aliyun, "_HAS_SDK", False)
        gw = aliyun.AliyunSmsGateway(
            app_id="", app_key="", sign_name="x", template_code="x"
        )
        with caplog.at_level(logging.INFO, logger="backend.integrations.sms.aliyun"):
            resp = _run(
                gw.send_notification(SmsSendRequest(phone=PHONE, template_id="1"))
            )
        assert resp.success is True
        assert PHONE not in caplog.text
