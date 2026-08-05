# tests/unit/test_f11_amount_override_audit.py
"""F11 回归测试：管理端代客下单金额覆盖审计

此前 order.amount 可被任意覆盖（0.01 元买年费）且操作日志仅"创建订单"无明细。
修复：范围校验（0 < amount ≤ 100000）+ 明细日志（订单号/系统价/实收价/操作人）
+ 偏离系统价 ±50% 超阈值告警。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import MemberStatus
from backend.database import Base
from backend.domain.child.models import Child
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


def _mk_trial_child(db):
    user = User(openid="f11user", phone="13800001111")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F11",
        age=7,
        grade="二年级",
        status=MemberStatus.TRIAL,
    )
    db.add(child)
    db.commit()
    return user, child


def _create_order(db, child, amount, admin_id=1):
    from backend.domain.admin.services.order_service import AdminOrderService

    return AdminOrderService(db).create_order(
        {
            "child_id": child.id,
            "order_type": 2,  # 观察期，系统价 500
            "amount": amount,
        },
        admin_id=admin_id,
    )


class TestAmountOverrideAudit:
    def test_override_logs_details(self, db):
        """覆盖金额 → OperationLog 含订单号/系统价/实收价/操作人"""
        from backend.domain.admin.models import OperationLog

        user, child = _mk_trial_child(db)
        result = _create_order(db, child, "450", admin_id=7)
        order_no = result.get("order_no")

        logs = (
            db.query(OperationLog)
            .filter(OperationLog.operation == "create_amount_override")
            .all()
        )
        assert len(logs) == 1
        content = logs[0].content
        assert order_no in content
        assert "系统价=500" in content
        assert "实收价=450" in content
        assert "操作人=7" in content

    def test_out_of_range_rejected(self, db):
        """0 元 / 超 10 万 → 422（ValidationError）"""
        from backend.common.exceptions import ValidationError

        user, child = _mk_trial_child(db)
        with pytest.raises(ValidationError):
            _create_order(db, child, "0")
        with pytest.raises(ValidationError):
            _create_order(db, child, "200000")

    def test_large_deviation_alerts(self, db):
        """覆盖价偏离系统价 ±50% 以上 → user_id=0 告警"""
        from backend.domain.message.models import SystemMessage

        user, child = _mk_trial_child(db)
        _create_order(db, child, "100")  # 系统价 500，偏离 80%

        alerts = (
            db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == 0,
                SystemMessage.title == "代客下单金额覆盖异常",
            )
            .count()
        )
        assert alerts == 1

    def test_normal_override_no_alert(self, db):
        """小幅覆盖（450 vs 500，偏离 10%）→ 有明细日志但无告警"""
        from backend.domain.admin.models import OperationLog
        from backend.domain.message.models import SystemMessage

        user, child = _mk_trial_child(db)
        _create_order(db, child, "450")

        logs = (
            db.query(OperationLog)
            .filter(OperationLog.operation == "create_amount_override")
            .count()
        )
        alerts = (
            db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == 0,
                SystemMessage.title == "代客下单金额覆盖异常",
            )
            .count()
        )
        assert logs == 1
        assert alerts == 0


class TestOfflineOrderAudit:
    """F11 P1：线下建单（create_offline_order）同类漏洞补齐"""

    def _offline_order(self, db, amount, admin_id=3, phone="13800001122"):
        from backend.domain.admin.services.order_service import AdminOrderService

        return AdminOrderService(db).create_offline_order(
            {
                "parent_name": "线下家长",
                "phone": phone,
                "child_name": "线下孩",
                "child_age": 7,
                "child_grade": "二年级",
                "order_type": 2,  # 观察期，系统价 500
                "amount": amount,
                "pay_type": 1,
            },
            admin_id=admin_id,
        )

    def test_offline_order_logs_details(self, db):
        """线下建单覆盖金额 → OperationLog 含订单号/系统价/实收价/操作人"""
        from backend.domain.admin.models import OperationLog

        result = self._offline_order(db, "450")
        order_no = result["order_no"]

        logs = (
            db.query(OperationLog)
            .filter(OperationLog.operation == "create_amount_override")
            .all()
        )
        assert len(logs) == 1
        content = logs[0].content
        assert order_no in content
        assert "系统价=500" in content
        assert "实收价=450" in content
        assert "操作人=3" in content

    def test_offline_order_out_of_range_rejected_upfront(self, db):
        """越界金额前置拒绝——不落用户/孩子/订单"""
        from backend.common.exceptions import ValidationError
        from backend.domain.user.models import User

        with pytest.raises(ValidationError):
            self._offline_order(db, "200000")
        assert db.query(User).count() == 0  # 前置校验，无孤儿数据

    def test_offline_order_large_deviation_alerts(self, db):
        """线下建单偏离系统价 ±50% 以上 → user_id=0 告警"""
        from backend.domain.message.models import SystemMessage

        self._offline_order(db, "100")  # 系统价 500，偏离 80%
        alerts = (
            db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == 0,
                SystemMessage.title == "代客下单金额覆盖异常",
            )
            .count()
        )
        assert alerts == 1

    def test_offline_order_normal_no_alert(self, db):
        """线下建单小幅覆盖（450 vs 500）→ 仅日志不告警"""
        from backend.domain.admin.models import OperationLog
        from backend.domain.message.models import SystemMessage

        self._offline_order(db, "450")
        logs = (
            db.query(OperationLog)
            .filter(OperationLog.operation == "create_amount_override")
            .count()
        )
        alerts = (
            db.query(SystemMessage)
            .filter(
                SystemMessage.user_id == 0,
                SystemMessage.title == "代客下单金额覆盖异常",
            )
            .count()
        )
        assert logs == 1
        assert alerts == 0
