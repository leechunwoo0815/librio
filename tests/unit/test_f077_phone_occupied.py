# tests/unit/test_f077_phone_occupied.py
"""F-077 账号接管回归测试（P2 最高危，方案 Y 定稿）

根因：wx_login 的 phone_code 链调 update_user_phone 时，手机号被他人占用 → 返回他人
用户 → 生成他人身份 token（同类漏改：change_phone 有防占用，wx_login 缺失）。

修复语义（专家定稿）：
  - update_user_phone 占用时统一抛 ConflictError（任何路径不得返回他人用户）
  - wx_login 捕获 ConflictError → openid 主身份照常登录（token 照发），跳过绑定，
    响应附 phone_occupied=True
"""

import asyncio

import pytest
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ConflictError
from backend.config import get_settings
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.user.router import wx_login
from backend.domain.user.schemas import UserLogin
from backend.domain.user.service import UserService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_user(db, openid, phone=None):
    u = User(openid=openid, phone=phone)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _decode_sub(token):
    settings = get_settings()
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )["sub"]


class TestF077PhoneOccupied:
    def test_update_user_phone_occupied_raises_conflict(self, db):
        """手机号被 A 占用 → B 绑定必须抛 ConflictError，禁止返回 A"""
        a = _mk_user(db, "openid_a", phone="13800000001")
        b = _mk_user(db, "openid_b")
        svc = UserService(db)

        with pytest.raises(ConflictError, match="已被其他账号绑定"):
            svc.update_user_phone(b.id, "13800000001")

        db.refresh(a)
        db.refresh(b)
        assert a.phone == "13800000001"
        assert b.phone is None

    def test_wx_login_occupied_returns_own_token_with_flag(self, db, monkeypatch):
        """B 用 A 已占用的手机号 wx_login → B 拿到 B 自己的 token + phone_occupied=True"""
        a = _mk_user(db, "openid_a", phone="13800000001")
        b = _mk_user(db, "openid_b")

        async def fake_code_to_session(code):
            return {"openid": "openid_b"}

        async def fake_get_phone_number(phone_code):
            return "13800000001"

        monkeypatch.setattr(
            "backend.domain.user.router.WeChatAuth.code_to_session",
            fake_code_to_session,
        )
        monkeypatch.setattr(
            "backend.domain.user.router.WeChatAuth.get_phone_number",
            fake_get_phone_number,
        )

        resp = asyncio.run(
            wx_login(UserLogin(code="wx-code", phone_code="wx-phone-code"),
                     UserService(db))
        )

        # B 拿到的是 B 自己的 openid 用户 token，绝非 A
        assert resp.phone_occupied is True
        assert resp.user.id == b.id
        assert resp.user.id != a.id
        assert _decode_sub(resp.token) == str(b.id)
        db.refresh(b)
        assert b.phone is None  # 占用时不绑定，也不篡改 B 的手机号

    def test_wx_login_unoccupied_binds_phone(self, db, monkeypatch):
        """手机号未被占用 → 正常绑定，phone_occupied=False"""
        c = _mk_user(db, "openid_c")

        async def fake_code_to_session(code):
            return {"openid": "openid_c"}

        async def fake_get_phone_number(phone_code):
            return "13900000002"

        monkeypatch.setattr(
            "backend.domain.user.router.WeChatAuth.code_to_session",
            fake_code_to_session,
        )
        monkeypatch.setattr(
            "backend.domain.user.router.WeChatAuth.get_phone_number",
            fake_get_phone_number,
        )

        resp = asyncio.run(
            wx_login(UserLogin(code="wx-code", phone_code="wx-phone-code"),
                     UserService(db))
        )

        assert resp.phone_occupied is False
        assert resp.user.id == c.id
        assert _decode_sub(resp.token) == str(c.id)
        db.refresh(c)
        assert c.phone == "13900000002"
