# tests/unit/test_subscribe_push.py
"""微信订阅消息推送管线（P1 触达闭环）— 降级安全 + 异步发送 + after_insert 接线

覆盖：
  1. 开关关闭/模板未配置/标题未命中/user_id=0 → 降级不发送（返回 False）
  2. 全条件满足 → 异步发送被调用（返回 True，WeChatSubscribe.send 收到 openid/模板/data）
  3. SystemMessage after_insert 钩子：真实插入触发推送检查，降级路径零副作用
"""

import time
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.message.models import SystemMessage
from backend.domain.user.models import User
from backend.integrations.wechat.config import SubscribeTemplate
from backend.integrations.wechat import subscribe as subscribe_mod
import backend.config as config_mod


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mk_user(db, openid=None):
    u = User(openid=openid or f"sub_{uuid.uuid4().hex[:8]}", parent_name="家长")
    db.add(u)
    db.commit()
    return u


def _enable_send(monkeypatch):
    """开启开关 + 填模板 + 拦截真实发送，返回调用记录"""
    sent = []

    class _FakeSettings:
        WECHAT_SUBSCRIBE_ENABLED = True

    async def _fake_send(openid, template_id, data, page=""):
        sent.append((openid, template_id, data))
        return {"errcode": 0}

    monkeypatch.setattr(config_mod, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(subscribe_mod.WeChatSubscribe, "send", _fake_send)
    return sent


class TestPushSubscribeMessage:
    def test_disabled_by_default(self, db):
        """默认开关关闭 → 不发送"""
        assert (
            subscribe_mod.push_subscribe_message("openid_x", "会员续费提醒", "x")
            is False
        )

    def test_template_not_configured_degrades(self, db, monkeypatch):
        """开关开但模板空 → 降级（返回 False，无网络调用）"""
        _enable_send(monkeypatch)
        monkeypatch.setattr(SubscribeTemplate, "MEMBER_EXPIRE_REMIND", "")
        assert (
            subscribe_mod.push_subscribe_message("openid_x", "会员续费提醒", "x")
            is False
        )

    def test_empty_openid_skips(self, db, monkeypatch):
        """openid 为空 → 不发送"""
        _enable_send(monkeypatch)
        monkeypatch.setattr(SubscribeTemplate, "MEMBER_EXPIRE_REMIND", "TMPL_M")
        assert subscribe_mod.push_subscribe_message("", "会员续费提醒", "x") is False

    def test_title_not_matched_skips(self, db, monkeypatch):
        """标题未命中高价值映射 → 不发送"""
        _enable_send(monkeypatch)
        monkeypatch.setattr(SubscribeTemplate, "MEMBER_EXPIRE_REMIND", "TMPL_M")
        assert (
            subscribe_mod.push_subscribe_message("openid_x", "普通系统消息", "x")
            is False
        )

    def test_async_send_called(self, db, monkeypatch):
        """全条件满足 → 异步发送被调用（openid/模板/数据正确）"""
        sent = _enable_send(monkeypatch)
        monkeypatch.setattr(SubscribeTemplate, "MEMBER_EXPIRE_REMIND", "TMPL_M")

        assert (
            subscribe_mod.push_subscribe_message(
                "openid_member",
                "会员续费提醒",
                "您的孩子 小明 的正式会员将在3天后到期",
            )
            is True
        )
        # 等待 daemon 线程执行
        for _ in range(20):
            if sent:
                break
            time.sleep(0.05)
        assert sent, "异步发送未在预期时间内执行"
        openid, template_id, data = sent[0]
        assert openid == "openid_member"
        assert template_id == "TMPL_M"
        assert "thing1" in data and "time3" in data

    def test_template_mapping(self, monkeypatch):
        """标题 → 模板映射命中规则"""
        monkeypatch.setattr(SubscribeTemplate, "MEMBER_EXPIRE_REMIND", "TMPL_M")
        monkeypatch.setattr(SubscribeTemplate, "RETURN_REMIND", "TMPL_R")
        assert subscribe_mod.get_template_for_title("会员续费提醒") == "TMPL_M"
        assert subscribe_mod.get_template_for_title("借阅到期提醒") == "TMPL_R"
        assert subscribe_mod.get_template_for_title("普通系统消息") == ""


class TestSystemMessageHook:
    def test_insert_triggers_hook_degrades(self, db):
        """SystemMessage 插入 → after_insert 钩子触发，降级路径零副作用"""
        u = _mk_user(db)
        msg = SystemMessage(
            user_id=u.id,
            title="会员续费提醒",
            content="测试内容",
            msg_type=1,
        )
        db.add(msg)
        db.commit()  # 若钩子抛异常，commit 会失败
        db.refresh(msg)
        assert msg.id is not None

    def test_insert_with_matching_template_sends(self, db, monkeypatch):
        """插入 + 开关开 + 模板配 → 钩子触发异步发送"""
        sent = _enable_send(monkeypatch)
        monkeypatch.setattr(SubscribeTemplate, "MEMBER_EXPIRE_REMIND", "TMPL_M")
        u = _mk_user(db, openid="openid_hook")
        msg = SystemMessage(
            user_id=u.id,
            title="会员续费提醒",
            content="3天后到期",
            msg_type=1,
        )
        db.add(msg)
        db.commit()
        for _ in range(20):
            if sent:
                break
            time.sleep(0.05)
        assert sent
        assert sent[0][0] == "openid_hook"
