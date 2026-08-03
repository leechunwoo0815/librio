# tests/unit/test_review_sla_config.py
"""P1-2 审核 SLA 配置化单测 — review_sla_hours 驱动 audit_sla_escalation"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401  # 注册 config_audit_log 表
from backend.bootstrap import register_event_handlers
from backend.common.config_service import ConfigService
from backend.common.types import MemberStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.refund.models import RefundApplication
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    yield session
    ConfigService.invalidate()  # 进程级缓存，测试间必须清理
    session.close()


def _mk_pending_refund(db, hours_old):
    user = User(openid="sla1", phone="13800004444")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id, name="SLA", age=7, grade="二年级", status=MemberStatus.OFFICIAL
    )
    db.add(child)
    db.commit()
    refund = RefundApplication(
        child_id=child.id,
        user_id=user.id,
        refund_amount=Decimal("100"),
        status=RefundApplication.STATUS_PENDING,
    )
    db.add(refund)
    db.commit()
    old = datetime.now() - timedelta(hours=hours_old)
    db.execute(
        text("UPDATE refund_application SET create_time=:t WHERE id=:i"),
        {"t": old, "i": refund.id},
    )
    db.commit()
    return refund


def _sla_alerts(db):
    return (
        db.query(SystemMessage)
        .filter(SystemMessage.title.like("审核超时提醒%"))
        .count()
    )


class TestReviewSlaHours:
    def test_default_24h_flags_stale(self, db):
        """默认 24h：30h 未审的退款应触发升级提醒"""
        from backend.tasks.scheduler import audit_sla_escalation

        _mk_pending_refund(db, hours_old=30)
        audit_sla_escalation(db)
        assert _sla_alerts(db) == 1

    def test_config_48h_not_flagged(self, db):
        """配置 48h 后：同一笔 30h 未审退款不再超时"""
        from backend.tasks.scheduler import audit_sla_escalation

        _mk_pending_refund(db, hours_old=30)
        ConfigService.set_config(db, "review_sla_hours", "48")
        ConfigService.invalidate("review_sla_hours")

        audit_sla_escalation(db)
        assert _sla_alerts(db) == 0

    def test_config_48h_flags_older(self, db):
        """配置 48h 后：50h 未审仍超时"""
        from backend.tasks.scheduler import audit_sla_escalation

        _mk_pending_refund(db, hours_old=50)
        ConfigService.set_config(db, "review_sla_hours", "48")
        ConfigService.invalidate("review_sla_hours")

        audit_sla_escalation(db)
        assert _sla_alerts(db) == 1
