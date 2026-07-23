# tests/unit/test_consent.py
"""同意记录（三段式监护人同意）单元测试"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.common.consent_texts import CONSENT_VERSION, get_consent_hash
from backend.domain.user.models import User
from backend.domain.user.consent_repository import ConsentRepository
from backend.domain.user.consent_service import ConsentService
from backend.common.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.domain.child.models import Child
from backend.domain.child.service import ChildService
from backend.domain.child.schemas import ChildCreate


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def user(db):
    openid = f"test_openid_{uuid.uuid4().hex[:8]}"
    u = User(openid=openid, parent_name="测试家长")
    db.add(u)
    db.flush()
    db.refresh(u)
    return u


@pytest.fixture
def child(db, user):
    c = Child(user_id=user.id, name="测试孩子", age=5, grade="中班")
    db.add(c)
    db.flush()
    db.refresh(c)
    return c


# ── consent_texts 测试 ──


class TestConsentTexts:
    def test_hash_deterministic(self):
        h1 = get_consent_hash("privacy_policy")
        h2 = get_consent_hash("privacy_policy")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_differs_by_type(self):
        h1 = get_consent_hash("privacy_policy")
        h2 = get_consent_hash("child_data")
        assert h1 != h2

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            get_consent_hash("nonexistent")

    def test_version_defined(self):
        assert CONSENT_VERSION == "v1.0"

    def test_texts_endpoint_returns_all_types(self):
        """GET /user/consent/texts 返回版本号与三类文案（前端弹窗唯一来源）"""
        from backend.domain.user.consent_router import get_consent_texts

        res = get_consent_texts()
        assert res["version"] == CONSENT_VERSION
        assert set(res["texts"].keys()) == {
            "privacy_policy",
            "child_data",
            "voice_recording",
        }
        for text in res["texts"].values():
            assert len(text) > 20


# ── consent service 测试 ──


class TestConsentService:
    def test_grant_consent(self, db, user):
        service = ConsentService(db)
        resp = service.grant_consent(user.id, "privacy_policy")
        assert resp.consent_type == "privacy_policy"
        assert resp.consent_version == CONSENT_VERSION
        assert resp.withdrawn_at is None

    def test_grant_invalid_type(self, db, user):
        service = ConsentService(db)
        with pytest.raises(ValidationError):
            service.grant_consent(user.id, "invalid_type")

    def test_has_valid_consent(self, db, user):
        service = ConsentService(db)
        assert not service.has_valid_consent(user.id, "voice_recording")
        service.grant_consent(user.id, "voice_recording")
        assert service.has_valid_consent(user.id, "voice_recording")

    def test_withdraw_consent(self, db, user):
        service = ConsentService(db)
        service.grant_consent(user.id, "privacy_policy")
        assert service.has_valid_consent(user.id, "privacy_policy")

        resp = service.withdraw_consent(user.id, "privacy_policy")
        assert resp.withdrawn_at is not None
        assert not service.has_valid_consent(user.id, "privacy_policy")

    def test_withdraw_child_data_rejected(self, db, user):
        service = ConsentService(db)
        service.grant_consent(user.id, "child_data")
        with pytest.raises(ValidationError, match="即将上线"):
            service.withdraw_consent(user.id, "child_data")

    def test_withdraw_nonexistent_raises(self, db, user):
        service = ConsentService(db)
        with pytest.raises(NotFoundError):
            service.withdraw_consent(user.id, "privacy_policy")

    def test_get_consents_returns_latest(self, db, user):
        service = ConsentService(db)
        service.grant_consent(user.id, "privacy_policy")
        service.grant_consent(user.id, "privacy_policy")  # second grant
        resp = service.get_consents(user.id)
        privacy_consents = [
            c for c in resp.consents if c.consent_type == "privacy_policy"
        ]
        assert len(privacy_consents) == 1  # only latest

    def test_record_fields_complete(self, db, user):
        service = ConsentService(db)
        resp = service.grant_consent(
            user.id, "child_data", ip_address="127.0.0.1", user_agent="TestAgent"
        )
        repo = ConsentRepository(db)
        record = repo.get_by_id(resp.id)
        assert record.user_id == user.id
        assert record.consent_type == "child_data"
        assert len(record.consent_text_hash) == 64
        assert record.consent_version == CONSENT_VERSION
        assert record.ip_address == "127.0.0.1"
        assert record.user_agent == "TestAgent"
        assert record.create_time is not None
        assert record.is_deleted == 0


# ── 拦截器测试：无同意创建孩子 403 ──


class TestChildConsentInterceptor:
    def test_create_child_without_consent_403(self, db, user):
        service = ChildService(db)
        data = ChildCreate(name="未同意孩子", age=4, grade="小班")
        with pytest.raises(ForbiddenError, match="请先同意") as exc_info:
            service.create_child(user.id, data)
        assert exc_info.value.error_code == "consent_required"

    def test_create_child_with_consent_201(self, db, user):
        consent_svc = ConsentService(db)
        consent_svc.grant_consent(user.id, "child_data")

        child_svc = ChildService(db)
        data = ChildCreate(name="已同意孩子", age=5, grade="中班")
        resp = child_svc.create_child(user.id, data)
        assert resp.name == "已同意孩子"

    def test_create_child_without_child_data_consent_403(self, db, user):
        """只有 privacy_policy 同意但没有 child_data 同意 → 403"""
        consent_svc = ConsentService(db)
        consent_svc.grant_consent(user.id, "privacy_policy")

        child_svc = ChildService(db)
        data = ChildCreate(name="缺同意孩子", age=6, grade="大班")
        with pytest.raises(ForbiddenError, match="请先同意") as exc_info:
            child_svc.create_child(user.id, data)
        assert exc_info.value.error_code == "consent_required"


# ── 拦截器测试：语音同意 ──


class TestVoiceConsentInterceptor:
    def test_voice_consent_required(self, db, user, child):
        service = ConsentService(db)
        assert not service.has_valid_consent(user.id, "voice_recording")

    def test_voice_consent_granted(self, db, user, child):
        service = ConsentService(db)
        service.grant_consent(user.id, "voice_recording")
        assert service.has_valid_consent(user.id, "voice_recording")

    def test_save_recording_without_voice_consent_403(self, db, user, child):
        """无 voice_recording 同意 → save_recording 403 + voice_consent_required"""
        from backend.domain.reading.schemas import SaveRecordingRequest
        from backend.domain.reading.service import ReadingService

        service = ReadingService(db)
        data = SaveRecordingRequest(
            child_id=child.id,
            book_id=1,
            text="hello world",
            audio_url="/uploads/voice/test.mp3",
            duration=5,
        )
        with pytest.raises(ForbiddenError, match="请先同意语音") as exc_info:
            service.save_recording(data)
        assert exc_info.value.error_code == "voice_consent_required"

    def test_save_recording_with_voice_consent_201(self, db, user, child):
        """有 voice_recording 同意 → save_recording 正常保存"""
        from backend.domain.reading.schemas import SaveRecordingRequest
        from backend.domain.reading.service import ReadingService

        ConsentService(db).grant_consent(user.id, "voice_recording")
        service = ReadingService(db)
        data = SaveRecordingRequest(
            child_id=child.id,
            book_id=1,
            text="hello world",
            audio_url="/uploads/voice/test.mp3",
            duration=5,
        )
        resp = service.save_recording(data)
        assert resp.audio_url == "/uploads/voice/test.mp3"
        assert resp.duration_seconds == 5


# ── 异常处理器 error_code 响应结构 ──


class TestErrorCodeResponse:
    def test_error_code_in_json_response(self):
        """ForbiddenError 带 error_code 时响应 JSON 含 error_code 字段"""
        import asyncio
        import json

        from backend.common.exceptions import business_exception_handler

        exc = ForbiddenError("请先同意儿童信息收集政策", error_code="consent_required")
        resp = asyncio.run(business_exception_handler(None, exc))
        body = json.loads(resp.body)
        assert resp.status_code == 403
        assert body["detail"] == "请先同意儿童信息收集政策"
        assert body["error_code"] == "consent_required"

    def test_no_error_code_key_when_unset(self):
        """不带 error_code 的异常响应不出现 error_code 键（向后兼容）"""
        import asyncio
        import json

        from backend.common.exceptions import business_exception_handler

        resp = asyncio.run(business_exception_handler(None, ForbiddenError("无权")))
        body = json.loads(resp.body)
        assert resp.status_code == 403
        assert "error_code" not in body
