"""批次 3 安全/权限回归：F-042/049/057/062/070/082"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.domain.parent_course_time.models  # noqa: F401
from backend.common.exceptions import ForbiddenError
from backend.database import Base
from backend.domain.admin.models import Admin
from backend.domain.admin.services.export_service import AdminExportService
from backend.domain.child.models import Child
from backend.domain.report.models import ObservationReport
from backend.domain.report.service import ReportService
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_user_child(db, openid="b3", phone="13800003001"):
    user = User(openid=openid, phone=phone)
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="B3", age=7, grade="一")
    db.add(child)
    db.commit()
    return user, child


class TestF042ReportOwnership:
    def test_mark_other_users_report_forbidden(self, db):
        from backend.domain.report.models import ObservationReport

        user_a, child_a = _mk_user_child(db, "b3a", "13800003001")
        user_b, _ = _mk_user_child(db, "b3b", "13800003002")
        report = ObservationReport(
            child_id=child_a.id,
            start_date=datetime.now() - timedelta(days=45),
            end_date=datetime.now(),
            status=ObservationReport.STATUS_GENERATED,
        )
        db.add(report)
        db.commit()
        svc = ReportService(db)
        with pytest.raises(ForbiddenError, match="无权操作"):
            svc.mark_observation_viewed(report.id, user_b.id)
        db.refresh(report)
        assert report.status == ObservationReport.STATUS_GENERATED  # 未被标记

    def test_mark_own_report_ok(self, db):
        user_a, child_a = _mk_user_child(db, "b3c", "13800003003")
        report = ObservationReport(
            child_id=child_a.id,
            start_date=datetime.now() - timedelta(days=45),
            end_date=datetime.now(),
            status=ObservationReport.STATUS_GENERATED,
        )
        db.add(report)
        db.commit()
        ReportService(db).mark_observation_viewed(report.id, user_a.id)
        db.refresh(report)
        assert report.status == ObservationReport.STATUS_VIEWED


class TestF049PageFailClosed:
    def test_unregistered_page_denied(self):
        from backend.domain.admin.admin_page_router import _check_page_perm

        admin = {"permissions": ["dashboard.view"]}
        assert _check_page_perm(admin, "not-a-page") is False  # fail-closed
        assert _check_page_perm(admin, "dashboard") is True

    def test_profile_and_403_are_whitelisted(self):
        """F-049 终审：profile 个人名片与 403 错误页必须放行（否则恒 403 / 无限重定向）"""
        from backend.domain.admin.admin_page_router import _check_page_perm

        admin = {"permissions": ["dashboard.view"]}
        assert _check_page_perm(admin, "profile") is True
        assert _check_page_perm(admin, "403") is True

    def test_profile_route_renders_for_authed_admin(self, db):
        """profile 页面路由不再 302 到 403（回归守护）"""
        import asyncio
        from unittest.mock import patch

        from backend.domain.admin.admin_page_router import (
            PAGE_PERM_MAP,
            profile,
        )

        assert PAGE_PERM_MAP.get("profile") == ""
        fake_admin = {"id": 1, "permissions": []}
        with patch(
            "backend.domain.admin.admin_page_router._get_admin_info",
            return_value=fake_admin,
        ), patch(
            "backend.domain.admin.admin_page_router.templates.TemplateResponse",
            return_value="RENDERED",
        ) as mock_render:
            from starlette.requests import Request

            request = Request({"type": "http", "method": "GET", "path": "/admin/view/profile"})
            resp = asyncio.run(profile(request))
        assert resp == "RENDERED"
        assert mock_render.call_args[0][1] == "admin/profile.html"


class TestF057QuizNoAnswerLeak:
    def test_public_question_response_has_no_answer(self):
        from backend.domain.advancement.schemas import QuestionPublicResponse

        fields = set(QuestionPublicResponse.model_fields.keys())
        assert "correct_answer" not in fields
        assert "explanation" not in fields


class TestF062AdminRoleLevel:
    def test_staff_cannot_create_staff(self, db):
        from backend.domain.admin.services.account_service import AdminAccountService

        staff = Admin(username="staff1", name="运营一号", role=1, status=1)
        staff.password_hash = "x"
        db.add(staff)
        db.commit()
        svc = AdminAccountService(db)
        with pytest.raises(ForbiddenError, match="无权创建"):
            svc.create_admin(
                SimpleNamespace(
                    username="new_staff",
                    name="n",
                    role=1,
                    admin_role_id=None,
                    teacher_id=None,
                    password="pass1234",
                ),
                current_admin_id=staff.id,
            )


class TestF070UserGroupMap:
    def test_expired_and_exited_mapped(self, db):
        from backend.domain.message.service import _get_user_groups

        user, child = _mk_user_child(db, "b3d", "13800003004")
        child.status = 3  # EXPIRED
        db.commit()
        assert "expired" in _get_user_groups(user.id, db)
        child.status = 4  # EXITED
        db.commit()
        assert "exited" in _get_user_groups(user.id, db)
        child.status = 5  # ALUMNI
        db.commit()
        assert "alumni" in _get_user_groups(user.id, db)


class TestF082CsvSafety:
    def test_users_export_no_openid_and_formula_guarded(self, db):
        user, _ = _mk_user_child(db, "b3e", "13800003005")
        user.parent_name = "=SUM(A1)"  # 公式注入样本
        db.commit()
        csv_content, filename = AdminExportService(db).export_data("users")
        assert "openid" not in csv_content.split("\n")[0]
        assert "b3e" not in csv_content  # openid 值不出现
        assert "'=SUM(A1)" in csv_content  # 公式注入加前缀


from types import SimpleNamespace  # noqa: E402
