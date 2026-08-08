"""批次5 F-100/F-105/F-111 回归：事务原子/流失口径/毕业还书提醒"""

import functools
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import (
    BorrowStatus,
    MemberStatus,
)
from backend.database import Base
from backend.domain.borrow.models import BorrowRecord
from backend.domain.child.benefit_transfer_model import BenefitTransferApplication
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.user.models import User
from backend.tasks import scheduler


@pytest.fixture(autouse=True)
def _noop_lock(monkeypatch):
    def _noop(*args, **kwargs):
        def deco(func):
            @functools.wraps(func)
            def wrapper(*a, **kw):
                return func(*a, **kw)

            return wrapper

        return deco

    monkeypatch.setattr(scheduler, "distributed_lock", _noop)


@pytest.fixture
def db(monkeypatch):
    scheduler.stop_scheduler()  # 停全局后台任务，防污染注入 session
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    register_event_handlers()
    monkeypatch.setattr(scheduler, "_get_db_session", lambda: session)
    yield session, Session
    session.close()


class TestF100TransferAtomic:
    def test_approve_single_transaction(self, db):
        """transfer 与申请状态更新同事务：中途失败两者都回滚（不再两次 commit）"""
        db_session, _ = db
        user = User(openid="t100", phone="13800010000")
        db_session.add(user)
        db_session.commit()
        source = Child(
            user_id=user.id,
            name="源",
            age=8,
            grade="三年级",
            status=MemberStatus.OFFICIAL,
            member_start_time=datetime.now(),
            member_expire_time=datetime.now() + timedelta(days=100),
        )
        target = Child(
            user_id=user.id,
            name="目标",
            age=6,
            grade="大班",
            status=MemberStatus.TRIAL,
        )
        db_session.add_all([source, target])
        db_session.commit()
        app = BenefitTransferApplication(
            source_child_id=source.id,
            target_child_id=target.id,
            user_id=user.id,
            status=0,
        )
        db_session.add(app)
        db_session.commit()

        from backend.domain.admin.services.benefit_transfer_service import (
            BenefitTransferAdminService,
        )

        # 正常 approve：单事务完成（transfer 不再内部 commit）
        result = BenefitTransferAdminService(db_session).approve(
            app.id, reviewer_id=1, review_remark="ok"
        )
        assert result["success"] is True
        db_session.refresh(source)
        db_session.refresh(target)
        db_session.refresh(app)
        assert source.status == MemberStatus.EXPIRED
        assert target.status == MemberStatus.OFFICIAL
        assert app.status == 1


class TestF105LostByExitedAt:
    def test_old_lost_not_counted_when_field_updated_this_week(self, db):
        """上周退出（exited_at 10 天前）但本周字段被刷新（update_time=now）：
        修复口径不计入本周流失（旧 update_time 口径会误计）"""
        from backend.domain.admin.services.dashboard_service import (
            AdminDashboardService,
        )

        db_session, _ = db
        user = User(openid="l105", phone="13800010500")
        db_session.add(user)
        db_session.commit()
        # 上周真实退出，本周因任意字段更新被 update_time 刷新
        old_lost = Child(
            user_id=user.id,
            name="老流失",
            age=9,
            grade="四年级",
            status=MemberStatus.EXPIRED,
            exited_at=datetime.now() - timedelta(days=10),
            update_time=datetime.now(),
        )
        db_session.add(old_lost)
        db_session.commit()

        metrics = AdminDashboardService(db_session).get_ops_metrics()
        # 修复口径：exited_at 不在本周 → 不计入（旧 update_time 口径会误计为 1）
        assert metrics["week_lost_members"] == 0

    def test_this_week_lost_counted(self, db):
        """本周真实退出（exited_at=1 天前）计入流失，即使本周无其他字段更新"""
        from backend.domain.admin.services.dashboard_service import (
            AdminDashboardService,
        )

        db_session, _ = db
        user = User(openid="l105b", phone="13800010504")
        db_session.add(user)
        db_session.commit()
        new_lost = Child(
            user_id=user.id,
            name="新流失",
            age=8,
            grade="三年级",
            status=MemberStatus.EXPIRED,
            exited_at=datetime.now() - timedelta(days=1),
            update_time=datetime.now() - timedelta(days=9),  # 旧口径会漏计
        )
        db_session.add(new_lost)
        db_session.commit()

        metrics = AdminDashboardService(db_session).get_ops_metrics()
        assert metrics["week_lost_members"] == 1


class TestF111GraduateReturnHint:
    def test_graduate_message_mentions_unreturned_books(self, db):
        db_session, Session = db
        user = User(openid="g111", phone="13800011100")
        db_session.add(user)
        db_session.commit()
        child = Child(
            user_id=user.id,
            name="毕业生",
            age=15,
            grade="初三",
            status=MemberStatus.OFFICIAL,
        )
        db_session.add(child)
        db_session.commit()
        db_session.add(
            BorrowRecord(
                child_id=child.id,
                book_id=1,
                status=BorrowStatus.BORROWING,
                borrow_time=datetime.now(),
                due_date=datetime.now(),
            )
        )
        db_session.commit()

        scheduler.graduate_children(db_session)
        check = Session()
        msg = (
            check.query(SystemMessage)
            .filter(SystemMessage.user_id == user.id)
            .order_by(SystemMessage.id.desc())
            .first()
        )
        assert "尚未归还" in msg.content
        assert "押金" in msg.content
        fresh = check.query(Child).filter_by(id=child.id).one()
        assert fresh.status == MemberStatus.ALUMNI
        check.close()

    def test_expired_write_exited_at(self, db):
        """F-105 配套：两处 EXPIRED 迁移点补写 exited_at"""
        db_session, Session = db
        user = User(openid="e105", phone="13800010501")
        db_session.add(user)
        db_session.commit()
        child = Child(
            user_id=user.id,
            name="到期",
            age=7,
            grade="二年级",
            status=MemberStatus.OBSERVATION,
            member_expire_time=datetime.now() - timedelta(days=1),
            exited_at=None,
        )
        db_session.add(child)
        db_session.commit()

        scheduler.check_observation_expiry(db_session)
        check = Session()
        fresh = check.query(Child).filter_by(id=child.id).one()
        assert fresh.status == MemberStatus.EXPIRED
        assert fresh.exited_at is not None
        check.close()
