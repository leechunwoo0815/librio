"""F-052 状态矩阵测试 — 管理端 FAILED 人工出路 + 矩阵外迁移守卫

覆盖 audit R3 X.8 差集：
  - FAILED→PAID / FAILED→CLOSED 两条矩阵边此前无直接测试（管理端人工改单唯一出口）
  - ALUMNI 毕业 / EXITED→TRIAL 复活为受控矩阵外迁移，行为已有测试锁定，本文件补回归
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.database import Base
from backend.domain.admin.services.order_service import AdminOrderService
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mk_failed_order(db) -> tuple[User, Child, Order]:
    user = User(openid="f052", phone="13800005200")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="矩阵",
        age=7,
        grade="二年级",
        status=MemberStatus.OBSERVATION,
    )
    db.add(child)
    db.commit()
    order = Order(
        order_no="MW-F052-001",
        user_id=user.id,
        child_id=child.id,
        type=OrderType.OBSERVATION,
        amount=Decimal("500.00"),
        pay_status=PayStatus.FAILED,
    )
    db.add(order)
    db.commit()
    return user, child, order


class TestFailedOrderManualExit:
    def test_failed_to_paid(self, db):
        """管理端人工出路：FAILED→PAID 成功 + 补支付时间 + F5 多孩快照"""
        user, child, order = _mk_failed_order(db)

        AdminOrderService(db).update_order_status(
            order.order_no, {"pay_status": PayStatus.PAID}
        )
        db.refresh(order)
        db.refresh(user)
        assert order.pay_status == PayStatus.PAID
        assert order.pay_time is not None
        # 观察期订单为会员类：支付成功入口必须落 F5 快照（4 入口全覆盖）
        assert user.paid_member_ever == 1

    def test_failed_to_closed(self, db):
        """管理端人工出路：FAILED→CLOSED 成功（关闭作废）"""
        user, child, order = _mk_failed_order(db)

        AdminOrderService(db).update_order_status(
            order.order_no, {"pay_status": PayStatus.CLOSED}
        )
        db.refresh(order)
        assert order.pay_status == PayStatus.CLOSED

    def test_failed_to_pending_rejected(self, db):
        """反向边：FAILED→PENDING 非法（矩阵外回退必须拒绝）"""
        from backend.common.exceptions import ValidationError

        user, child, order = _mk_failed_order(db)
        with pytest.raises(ValidationError, match="不允许"):
            AdminOrderService(db).update_order_status(
                order.order_no, {"pay_status": PayStatus.PENDING}
            )


class TestOutOfMatrixGuardedTransitions:
    def test_revive_requires_super_admin_confirm(self, db):
        """F13：EXITED→TRIAL 复活是受控矩阵外入口——普通权限/无确认必须拒绝"""
        from backend.common.exceptions import ValidationError
        from backend.domain.admin.services.guardian_service import GuardianService

        user = User(openid="f052r", phone="13800005201")
        db.add(user)
        db.commit()
        child = Child(
            user_id=user.id,
            name="复活",
            age=7,
            grade="二年级",
            status=MemberStatus.EXITED,
            exited_at=None,
        )
        db.add(child)
        db.commit()

        # 无 confirmed 参数直接走 revive 触发二次确认校验
        with pytest.raises(ValidationError, match="二次确认"):
            GuardianService(db).revive_child(child.id, admin_id=1, confirmed=False)

    def test_graduate_marks_alumni_with_guard(self, db, monkeypatch):
        """F-046：graduate_children 满 15 岁 OFFICIAL → ALUMNI"""
        from backend.tasks import scheduler
        import functools

        def _noop(*args, **kwargs):
            def deco(func):
                @functools.wraps(func)
                def wrapper(*a, **kw):
                    return func(*a, **kw)

                return wrapper

            return deco

        monkeypatch.setattr(scheduler, "distributed_lock", _noop)
        user = User(openid="f052g", phone="13800005202")
        db.add(user)
        db.commit()
        child = Child(
            user_id=user.id,
            name="毕业",
            age=15,
            grade="初二",
            status=MemberStatus.OFFICIAL,
        )
        db.add(child)
        db.commit()

        # 正常路径：满 15 岁 OFFICIAL → ALUMNI
        scheduler.graduate_children(db)
        db.refresh(child)
        assert child.status == MemberStatus.ALUMNI

    def test_graduate_skips_exited_child(self, db, monkeypatch):
        """F-046 守卫反例：毕业生队列收集后/运行前被置 EXITED，重查守卫不得毕业"""
        from backend.tasks import scheduler
        import functools

        def _noop(*args, **kwargs):
            def deco(func):
                @functools.wraps(func)
                def wrapper(*a, **kw):
                    return func(*a, **kw)

                return wrapper

            return deco

        monkeypatch.setattr(scheduler, "distributed_lock", _noop)
        user = User(openid="f052g2", phone="13800005203")
        db.add(user)
        db.commit()
        child = Child(
            user_id=user.id,
            name="退出生",
            age=15,
            grade="初二",
            status=MemberStatus.EXITED,
        )
        db.add(child)
        db.commit()

        scheduler.graduate_children(db)
        db.refresh(child)
        assert child.status == MemberStatus.EXITED
