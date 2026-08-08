# tests/unit/test_f046_scheduler_guards.py
"""F-046 scheduler 状态写守卫回归测试

5 处直改状态补"写前重取+行锁+状态前置"（对齐 F58 mark_overdue_books 范本）：
check_grace_period_shutdown / migrate_activity_status×3 / alert_stale_refunds /
graduate_children / check_observation_expiry。并发场景由 MySQL 场景 G 实证。
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
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
    yield session
    session.close()


class TestF046SchedulerGuards:
    def test_grace_shutdown_expires_overdue_official(self, tmp_path, monkeypatch):
        from backend.tasks.scheduler import check_grace_period_shutdown

        engine = create_engine(f"sqlite:///{tmp_path}/grace.db")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        s = Session()
        user = User(openid="f046user", phone="13800004601")
        s.add(user)
        s.commit()
        child = Child(
            user_id=user.id,
            name="F046",
            age=7,
            grade="二年级",
            status=MemberStatus.OFFICIAL,
            member_expire_time=datetime.now() - timedelta(days=20),
        )
        s.add(child)
        s.commit()
        child_id = child.id
        s.close()
        # 注入文件库会话工厂（任务函数自开 session 并在 finally close）
        monkeypatch.setattr("backend.database.get_session", lambda: Session)
        check_grace_period_shutdown()
        s2 = Session()
        c = s2.query(Child).filter(Child.id == child_id).first()
        assert c.status == MemberStatus.EXPIRED

    def test_graduate_repeated_run_idempotent(self, db):
        from backend.tasks.scheduler import graduate_children

        user = User(openid="f046g", phone="13800004603")
        db.add(user)
        db.commit()
        child = Child(
            user_id=user.id,
            name="G",
            age=15,
            grade="二",
            status=MemberStatus.OFFICIAL,
        )
        db.add(child)
        db.commit()
        graduate_children(db)
        graduate_children(db)  # 重复运行：ALUMNI 不再被处理
        db.refresh(child)
        assert child.status == MemberStatus.ALUMNI

    def test_observation_expiry_only_for_observation(self, db):
        """非 OBSERVATION 状态不被到期任务覆盖（守卫行为）"""
        from backend.tasks.scheduler import check_observation_expiry

        user = User(openid="f046o", phone="13800004604")
        db.add(user)
        db.commit()
        child = Child(
            user_id=user.id,
            name="O",
            age=7,
            grade="二",
            status=MemberStatus.EXPIRED,
            member_expire_time=datetime.now() - timedelta(days=1),
        )
        db.add(child)
        db.commit()
        check_observation_expiry(db)
        db.refresh(child)
        assert child.status == MemberStatus.EXPIRED  # 不变（守卫/查询过滤）
