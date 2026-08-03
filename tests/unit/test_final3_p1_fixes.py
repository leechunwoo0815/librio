# tests/unit/test_final3_p1_fixes.py
"""终审 FINAL-3.0 P1 修复单测 — exited_at 钩子 / paid_member_ever 快照 /
teacher.workbench 权限 / 工作台页面冒烟"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    session.close()


def _mk_user_child(db, openid="f3"):
    user = User(openid=openid, phone=f"138{abs(hash(openid)) % 10**8:08d}")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F3",
        age=7,
        grade="二年级",
        status=MemberStatus.OBSERVATION,
    )
    db.add(child)
    db.commit()
    return user, child


# ---------------------------------------------------------------- P1-2
class TestExitedAtHooks:
    def test_update_status_to_exited_sets_exited_at(self, db):
        from backend.domain.child.schemas import ChildStatusUpdate
        from backend.domain.child.service import ChildService

        _, child = _mk_user_child(db)
        assert child.exited_at is None
        ChildService(db).update_status(
            child.id, ChildStatusUpdate(status=MemberStatus.EXITED)
        )
        db.refresh(child)
        assert child.exited_at is not None

    def test_exited_at_not_overwritten_on_second_exit(self, db):
        """exited_at 只写一次（EXITED→其他→EXITED 场景不重置计时）"""
        from backend.domain.child.schemas import ChildStatusUpdate
        from backend.domain.child.service import ChildService

        _, child = _mk_user_child(db)
        svc = ChildService(db)
        svc.update_status(child.id, ChildStatusUpdate(status=MemberStatus.EXITED))
        first = child.exited_at
        assert first is not None
        # 直接改回 OBSERVATION（绕过状态机模拟数据修正场景），再次 EXITED
        child.status = MemberStatus.OBSERVATION
        db.commit()
        svc.update_status(child.id, ChildStatusUpdate(status=MemberStatus.EXITED))
        db.refresh(child)
        assert child.exited_at == first  # 未重置

    def test_revive_clears_exited_at(self, db):
        from backend.domain.admin.services.guardian_service import GuardianService

        _, child = _mk_user_child(db)
        child.status = MemberStatus.EXITED
        child.exited_at = datetime.now()
        db.commit()
        GuardianService(db).revive_child(child.id, admin_id=1)
        db.refresh(child)
        assert child.status == MemberStatus.TRIAL
        assert child.exited_at is None


# ---------------------------------------------------------------- P1-3
class TestPaidMemberEver:
    def _mk_paid_order(self, db, user, child, order_type=OrderType.OBSERVATION):
        order = Order(
            order_no="MW-F3-001",
            user_id=user.id,
            child_id=child.id,
            type=order_type,
            amount=Decimal("500"),
            pay_status=PayStatus.PENDING,
        )
        db.add(order)
        db.commit()
        return order

    def test_callback_sets_flag(self, db):
        from backend.domain.order.schemas import OrderPayCallback
        from backend.domain.order.service import OrderService

        user, child = _mk_user_child(db)
        order = self._mk_paid_order(db, user, child)
        assert user.paid_member_ever == 0

        OrderService(db).handle_payment_callback(
            OrderPayCallback(
                order_no=order.order_no,
                trade_no="T1",
                pay_type=1,
                amount=Decimal("500"),
            )
        )
        db.refresh(user)
        assert user.paid_member_ever == 1

    def test_parent_course_does_not_set_flag(self, db):
        from backend.domain.order.schemas import OrderPayCallback
        from backend.domain.order.service import OrderService

        user, child = _mk_user_child(db)
        order = self._mk_paid_order(db, user, child, order_type=OrderType.PARENT_COURSE)
        OrderService(db).handle_payment_callback(
            OrderPayCallback(
                order_no=order.order_no,
                trade_no="T2",
                pay_type=1,
                amount=Decimal("500"),
            )
        )
        db.refresh(user)
        assert user.paid_member_ever == 0

    def test_discount_via_flag_after_orders_purged(self, db):
        """F5 冲突解决：订单被 purge 删除后，快照列仍让多孩折扣生效"""
        from backend.domain.order.service import OrderService

        user, child = _mk_user_child(db)
        user.paid_member_ever = 1
        db.commit()
        # 无订单（模拟 purge 后），新孩子报名仍享多孩 9 折
        svc = OrderService(db)
        price = svc._apply_discount(
            user_id=user.id,
            order_type=OrderType.OFFICIAL_MEMBER,
            amount=Decimal("5400"),
            child_status=MemberStatus.TRIAL,
            child_id=child.id,
        )
        assert price == Decimal("4860.00")

    def test_no_discount_without_flag_or_orders(self, db):
        from backend.domain.order.service import OrderService

        user, child = _mk_user_child(db)
        price = OrderService(db)._apply_discount(
            user_id=user.id,
            order_type=OrderType.OFFICIAL_MEMBER,
            amount=Decimal("5400"),
            child_status=MemberStatus.TRIAL,
            child_id=child.id,
        )
        assert price == Decimal("5400")


# ---------------------------------------------------------------- P2 权限与工作台
class TestTeacherWorkbenchPerm:
    def test_permission_seeded(self):
        from backend.seeds.seed_rbac import PERMISSIONS, TEACHER_PERMS

        codes = {p["code"] for p in PERMISSIONS}
        assert "teacher.workbench" in codes
        assert "teacher.workbench" in TEACHER_PERMS
        assert "teacher.workbench" not in {
            c for c in TEACHER_PERMS if c.startswith("dashboard")
        }

    def test_page_perm_map_uses_dedicated_perm(self):
        from backend.domain.admin.admin_page_router import PAGE_PERM_MAP

        assert PAGE_PERM_MAP["teacher-workbench"] == "teacher.workbench"

    def test_workbench_page_redirects_when_unauthenticated(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        client = TestClient(app)
        resp = client.get("/admin/view/teacher-workbench", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/view/login" in resp.headers["location"]

    def test_workbench_template_renders(self):
        """Jinja 渲染冒烟：模板语法 + 必需区块存在（终审 P2-11）"""
        import os

        from starlette.templating import Jinja2Templates

        template_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "backend", "templates"
        )
        templates = Jinja2Templates(directory=template_dir)
        tpl = templates.get_template("admin/teacher_workbench.html")
        html = tpl.render(
            request=None,
            active_page="teacher-workbench",
            admin={"name": "T", "permissions": ["teacher.workbench"]},
            user_can=lambda code: True,
        )
        assert 'data-action="submit-feedback"' in html
        assert "feedbackChild" in html
        assert "老师工作台" in html
