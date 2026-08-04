# tests/unit/test_f14_observation_report_compensation.py
"""F14 回归测试：观察期报告失败补偿 + 到期/报告判定单口径

约束（专家裁定）：
  ① 报告生成失败不得先改状态——整批回滚、下轮重试，杜绝"状态已 EXPIRED 而报告永久丢失"；
  ② 到期判定与报告判定统一用 member_expire_time，废掉 member_start_time + observation_days 推算口径。
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
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


def _mk_observation_child(db, openid, expire_delta):
    user = User(openid=openid, phone=f"138{abs(hash(openid)) % 10**8:08d}")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="报告",
        age=7,
        grade="二年级",
        status=MemberStatus.OBSERVATION,
        member_start_time=datetime.now() - timedelta(days=46),
        member_expire_time=datetime.now() + expire_delta,
    )
    db.add(child)
    db.commit()
    return user, child


class TestUnifiedExpiryAndReport:
    def test_future_expire_no_report_no_expired(self, db):
        """member_start 46 天前但 expire 在未来（管理员延长）→ 不生成报告、不转 EXPIRED"""
        from backend.domain.report.service import ReportService
        from backend.tasks.scheduler import check_observation_expiry

        user, child = _mk_observation_child(db, "f14future", timedelta(days=10))

        assert ReportService(db).generate_due_reports() == []
        check_observation_expiry(db)
        db.refresh(child)
        assert child.status == MemberStatus.OBSERVATION

    def test_past_expire_generates_report_and_expires(self, db):
        """expire 已过 → 生成报告 + 转 EXPIRED"""
        from backend.domain.report.service import ReportService
        from backend.tasks.scheduler import check_observation_expiry

        user, child = _mk_observation_child(db, "f14due", timedelta(days=-1))

        check_observation_expiry(db)

        db.refresh(child)
        assert child.status == MemberStatus.EXPIRED
        assert ReportService(db).get_report(child.id) is not None


class TestReportFailureAbortsStatusChange:
    def test_generation_failure_keeps_status_then_retry_succeeds(self, db, monkeypatch):
        """报告生成失败 → 整批回滚（状态不变）；下轮重试成功"""
        from backend.domain.report.service import ReportService
        from backend.tasks.scheduler import check_observation_expiry

        user, child = _mk_observation_child(db, "f14fail", timedelta(days=-1))

        def boom(self):
            raise RuntimeError("观察期报告生成失败（模拟）")

        monkeypatch.setattr(ReportService, "generate_due_reports", boom)
        check_observation_expiry(db)

        db.refresh(child)
        assert child.status == MemberStatus.OBSERVATION  # 状态未先改

        monkeypatch.undo()
        check_observation_expiry(db)  # 下轮重试

        db.refresh(child)
        assert child.status == MemberStatus.EXPIRED
        assert ReportService(db).get_report(child.id) is not None
