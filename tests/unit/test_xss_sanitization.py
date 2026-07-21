# tests/unit/test_xss_sanitization.py
"""XSS 防护回归测试——每个修复点对应 payload 注入断言"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.advancement.models import Level, ChildLevel
from backend.domain.report.service import ReportService
from backend.domain.certificate.models import LevelCertificate
from backend.domain.certificate.service import CertificateService
from backend.domain.admin.admin_schemas import (
    BulkImportBookItem,
    CreateLevelRequest,
    UpdateLevelRequest,
    CreateAchievementRequest,
    UpdateAchievementRequest,
    SendMessageRequest,
)

XSS_PAYLOAD = 'x"><img src=x onerror=alert(1)>'


# ==================== Fixtures ====================


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ==================== X1: Jinja2 autoescape ====================


def test_observation_report_autoescape_child_name(db):
    """X1: child_name 含 XSS payload 渲染后应为转义形式"""
    user = User(openid="xss_user1", phone="13800138101")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name=XSS_PAYLOAD,
        age=6,
        grade="一年级",
        status=Child.STATUS_OBSERVATION,
        create_time=datetime.now() - timedelta(days=31),
        member_start_time=datetime.now() - timedelta(days=31),
    )
    db.add(child)
    db.commit()

    level = Level(name="A", sort_order=1, required_books=10, max_borrow_count=20)
    db.add(level)
    db.commit()

    cl = ChildLevel(child_id=child.id, level_id=level.id, is_current=True)
    db.add(cl)
    db.commit()

    svc = ReportService(db)
    svc.generate_due_reports()
    html = svc.render_report_html(child.id)
    assert html is not None, "报告渲染不应为空"
    assert XSS_PAYLOAD not in html, f"原始 payload 不应出现在 HTML 中: {XSS_PAYLOAD}"
    # payload 中的 < > " 必须被转义（Jinja2 autoescape 会转义 & < > " '）
    assert "&lt;" in html, "payload 中的 < 应被转义为 &lt;"
    assert "&gt;" in html, "payload 中的 > 应被转义为 &gt;"
    assert "&quot;" in html or "&#34;" in html, 'payload 中的 " 应被转义为 &quot;'


def test_observation_report_autoescape_teacher_comment(db):
    """X1: teacher_comment 含 XSS payload -> 模板内 teacher_comment_section 被 | safe 放行应保持 HTML"""
    user = User(openid="xss_user2", phone="13800138102")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="SafeChild",
        age=6,
        grade="一年级",
        status=Child.STATUS_OBSERVATION,
        create_time=datetime.now() - timedelta(days=31),
        member_start_time=datetime.now() - timedelta(days=31),
    )
    db.add(child)
    db.commit()

    level = Level(name="A", sort_order=1, required_books=10, max_borrow_count=20)
    db.add(level)
    db.commit()

    svc = ReportService(db)
    svc.generate_due_reports()
    report = svc.get_report(child.id)
    assert report is not None

    # teacher_comment 是 service 层拼装的 HTML 片段（含 <div>）
    safe_html_fragment = '<div class="teacher-note">表现优秀</div>'
    svc.add_teacher_comment(report["id"], teacher_id=1, comment=safe_html_fragment)

    html = svc.render_report_html(child.id)
    assert html is not None
    # teacher_comment_section 被 | safe 放行，所以 <div> 不被转义
    assert '<div class="teacher-note">' in html, (
        "teacher_comment_section 应保持 HTML（| safe）"
    )


def test_certificate_autoescape_child_name(db):
    """X1: 证书 child_name 含 XSS payload 渲染后应为转义形式"""
    user = User(openid="xss_user3", phone="13800138103")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name=XSS_PAYLOAD,
        age=7,
        grade="二年级",
        status=Child.STATUS_OFFICIAL,
    )
    db.add(child)
    db.commit()

    level = Level(name="A", sort_order=1, required_books=10, max_borrow_count=20)
    db.add(level)
    db.commit()

    cert = LevelCertificate(
        child_id=child.id,
        level_id=level.id,
        child_name=XSS_PAYLOAD,
        child_english_name="Test",
        level_name="A",
        certificate_no="CERT-XSS-001",
        create_time=datetime.now(),
    )
    db.add(cert)
    db.commit()

    svc = CertificateService(db)
    html = svc.render_certificate_html(cert.id)
    assert html is not None, "证书渲染不应为空"
    assert XSS_PAYLOAD not in html, "原始 payload 不应出现在证书 HTML 中"
    assert "&lt;" in html or "&gt;" in html, "payload 中的 < > 应被转义"


# ==================== X5: Schema 校验 ====================


class TestSchemaValidation:
    """X5: 后端 schema 校验——拒绝恶意输入"""

    def test_bulk_import_isbn_too_long(self):
        """BulkImportBookItem.isbn 超长应拒绝"""
        with pytest.raises(ValidationError):
            BulkImportBookItem(isbn="9" * 21)  # max_length=20

    def test_bulk_import_isbn_ok(self):
        """BulkImportBookItem.isbn 合法应通过"""
        item = BulkImportBookItem(isbn="9780123456789")
        assert item.isbn == "9780123456789"

    def test_level_badge_emoji_too_long(self):
        """CreateLevelRequest.badge_emoji 超长应拒绝"""
        with pytest.raises(ValidationError):
            CreateLevelRequest(name="X", badge_emoji="E" * 21)  # max_length=20

    def test_level_badge_emoji_ok(self):
        """CreateLevelRequest.badge_emoji 合法应通过"""
        req = CreateLevelRequest(name="A", badge_emoji="🌟")
        assert req.badge_emoji == "🌟"

    def test_update_level_badge_emoji_too_long(self):
        """UpdateLevelRequest.badge_emoji 超长应拒绝"""
        with pytest.raises(ValidationError):
            UpdateLevelRequest(badge_emoji="L" * 21)

    def test_achievement_badge_emoji_too_long(self):
        """CreateAchievementRequest.badge_emoji 超长应拒绝"""
        with pytest.raises(ValidationError):
            CreateAchievementRequest(name="X", type=1, badge_emoji="B" * 21)

    def test_update_achievement_badge_emoji_too_long(self):
        """UpdateAchievementRequest.badge_emoji 超长应拒绝"""
        with pytest.raises(ValidationError):
            UpdateAchievementRequest(badge_emoji="L" * 21)

    def test_target_role_groups_invalid_value(self):
        """SendMessageRequest.target_role_groups 含无效枚举应拒绝"""
        with pytest.raises(ValidationError, match="无效用户分组"):
            SendMessageRequest(
                title="test",
                content="test",
                target="all",
                target_role_groups=["invalid_group"],
            )

    def test_target_role_groups_valid_values(self):
        """SendMessageRequest.target_role_groups 合法枚举应通过"""
        req = SendMessageRequest(
            title="test",
            content="test",
            target="all",
            target_role_groups=["trial", "observation", "member"],
        )
        assert req.target_role_groups == ["trial", "observation", "member"]

    def test_target_role_groups_none(self):
        """SendMessageRequest.target_role_groups=None 应通过"""
        req = SendMessageRequest(title="test", content="test", target="all")
        assert req.target_role_groups is None
