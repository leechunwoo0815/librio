# tests/unit/test_data_retention.py
"""H5 数据保留期 purge 任务单测 — 终审 P0-3

覆盖边界：到期删除 / 未到期保留 / EXITED 才删行为数据 / consent_record 豁免 /
消息级联 / 语音 6 个月 / 财务 5 年门槛。
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import DepositStatus, MemberStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.deposit.models import DepositRecord
from backend.domain.message.models import (
    MessageReadStatus,
    SystemMessage,
    TeacherMessage,
)
from backend.domain.reading.models import CheckIn, VoiceRecording
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


def _mk_user_child(db, status=MemberStatus.OFFICIAL, openid="ret1", exited_at=None):
    user = User(openid=openid, phone=f"138{abs(hash(openid)) % 10**8:08d}")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="保留",
        age=7,
        grade="二年级",
        status=status,
        exited_at=exited_at,
    )
    db.add(child)
    db.commit()
    return user, child


def _age(db, model, obj_id, days):
    """把记录 create_time 改老（绕过 ORM default）"""
    old = datetime.now() - timedelta(days=days)
    db.execute(
        text(f"UPDATE {model.__tablename__} SET create_time=:t WHERE id=:i"),
        {"t": old, "i": obj_id},
    )
    db.commit()


class TestMessageRetention:
    def test_old_messages_purged_recent_kept(self, db):
        from backend.tasks.scheduler import purge_expired_data

        user, _ = _mk_user_child(db)
        old_msg = SystemMessage(user_id=user.id, title="旧", content="c", msg_type=1)
        new_msg = SystemMessage(user_id=user.id, title="新", content="c", msg_type=1)
        db.add_all([old_msg, new_msg])
        db.commit()
        _age(db, SystemMessage, old_msg.id, 400)  # 400 天 > 1 年
        _age(db, SystemMessage, new_msg.id, 100)

        stats = purge_expired_data(db)
        assert stats.get("system_message") == 1
        titles = [m.title for m in db.query(SystemMessage).all()]
        assert titles == ["新"]

    def test_read_status_cascaded(self, db):
        from backend.tasks.scheduler import purge_expired_data

        user, _ = _mk_user_child(db)
        msg = SystemMessage(user_id=None, title="群发", content="c", msg_type=1)
        db.add(msg)
        db.commit()
        rs = MessageReadStatus(message_id=msg.id, user_id=user.id)
        db.add(rs)
        db.commit()
        _age(db, SystemMessage, msg.id, 400)

        stats = purge_expired_data(db)
        assert stats.get("message_read_status") == 1
        assert db.query(MessageReadStatus).count() == 0
        assert db.query(SystemMessage).count() == 0

    def test_teacher_message_purged(self, db):
        from backend.tasks.scheduler import purge_expired_data

        tm = TeacherMessage(teacher_id=1, title="旧通知", content="c", msg_type=1)
        db.add(tm)
        db.commit()
        _age(db, TeacherMessage, tm.id, 400)
        stats = purge_expired_data(db)
        assert stats.get("teacher_message") == 1
        assert db.query(TeacherMessage).count() == 0

    def test_admin_alert_user_id_0_exempt(self, db):
        """终审 P2：user_id=0 管理端告警豁免清理（审计链保留），群发/普通消息照常"""
        from backend.tasks.scheduler import purge_expired_data

        user, _ = _mk_user_child(db)
        admin_alert = SystemMessage(user_id=0, title="SLA告警", content="c", msg_type=1)
        broadcast = SystemMessage(user_id=None, title="群发", content="c", msg_type=1)
        personal = SystemMessage(user_id=user.id, title="个人", content="c", msg_type=1)
        db.add_all([admin_alert, broadcast, personal])
        db.commit()
        for m in (admin_alert, broadcast, personal):
            _age(db, SystemMessage, m.id, 400)

        stats = purge_expired_data(db)
        assert stats.get("system_message") == 2  # 群发+个人被清，告警豁免
        remaining = {m.title for m in db.query(SystemMessage).all()}
        assert remaining == {"SLA告警"}


class TestBehaviorRetention:
    def test_exited_child_behavior_purged_after_2y(self, db):
        from backend.tasks.scheduler import purge_expired_data

        old_exit = datetime.now() - timedelta(days=800)
        _, exited = _mk_user_child(
            db, status=MemberStatus.EXITED, openid="ret2", exited_at=old_exit
        )
        _, active = _mk_user_child(db, status=MemberStatus.OFFICIAL, openid="ret3")
        for c in (exited, active):
            db.add(
                CheckIn(child_id=c.id, check_date=datetime.now().date(), check_type=1)
            )
        db.commit()

        stats = purge_expired_data(db)
        assert stats.get("check_in") == 1
        remaining = {c.child_id for c in db.query(CheckIn).all()}
        assert remaining == {active.id}

    def test_recently_exited_kept(self, db):
        from backend.tasks.scheduler import purge_expired_data

        recent_exit = datetime.now() - timedelta(days=100)
        _, exited = _mk_user_child(
            db, status=MemberStatus.EXITED, openid="ret4", exited_at=recent_exit
        )
        db.add(
            CheckIn(child_id=exited.id, check_date=datetime.now().date(), check_type=1)
        )
        db.commit()

        stats = purge_expired_data(db)
        assert stats.get("check_in", 0) == 0
        assert db.query(CheckIn).count() == 1

    def test_field_refresh_does_not_delay_purge(self, db):
        """终审 P1-2 反例：EXITED 后字段被刷新（update_time 变新）不影响 exited_at 计时"""
        from backend.tasks.scheduler import purge_expired_data

        old_exit = datetime.now() - timedelta(days=800)
        _, exited = _mk_user_child(
            db, status=MemberStatus.EXITED, openid="ret8", exited_at=old_exit
        )
        db.add(
            CheckIn(child_id=exited.id, check_date=datetime.now().date(), check_type=1)
        )
        db.commit()
        # 模拟对账任务/管理员编辑刷新字段（update_time 被 onupdate 刷新为现在）
        exited.total_reading_minutes = 999
        db.commit()
        db.refresh(exited)
        assert exited.update_time > old_exit  # update_time 已变新

        stats = purge_expired_data(db)
        assert stats.get("check_in") == 1  # 仍按 exited_at 判定，照样清理

    def test_exited_at_null_legacy_not_purged(self, db):
        """存量无 exited_at 的 EXITED 行不清理（迁移已回填，此处兜底验证）"""
        from backend.tasks.scheduler import purge_expired_data

        _, exited = _mk_user_child(
            db, status=MemberStatus.EXITED, openid="ret9", exited_at=None
        )
        db.add(
            CheckIn(child_id=exited.id, check_date=datetime.now().date(), check_type=1)
        )
        db.commit()

        stats = purge_expired_data(db)
        assert stats.get("check_in", 0) == 0
        assert db.query(CheckIn).count() == 1


class TestFinanceRetention:
    def test_finance_kept_within_5y_even_if_exited(self, db):
        from backend.tasks.scheduler import purge_expired_data

        old_exit = datetime.now() - timedelta(days=800)
        _, exited = _mk_user_child(
            db, status=MemberStatus.EXITED, openid="ret5", exited_at=old_exit
        )
        dep = DepositRecord(
            child_id=exited.id, amount=Decimal("1200"), status=DepositStatus.PAID
        )
        db.add(dep)
        db.commit()
        _age(db, DepositRecord, dep.id, 800)  # 2 年前（<5 年）

        stats = purge_expired_data(db)
        assert stats.get("deposit_record", 0) == 0
        assert db.query(DepositRecord).count() == 1

    def test_finance_purged_after_5y_for_exited(self, db):
        from backend.tasks.scheduler import purge_expired_data

        old_exit = datetime.now() - timedelta(days=800)
        _, exited = _mk_user_child(
            db, status=MemberStatus.EXITED, openid="ret6", exited_at=old_exit
        )
        dep = DepositRecord(
            child_id=exited.id, amount=Decimal("1200"), status=DepositStatus.PAID
        )
        db.add(dep)
        db.commit()
        _age(db, DepositRecord, dep.id, 2000)  # >5 年

        stats = purge_expired_data(db)
        assert stats.get("deposit_record") == 1
        assert db.query(DepositRecord).count() == 0

    def test_finance_never_purged_for_active_child(self, db):
        from backend.tasks.scheduler import purge_expired_data

        _, active = _mk_user_child(db, status=MemberStatus.OFFICIAL, openid="ret7")
        dep = DepositRecord(
            child_id=active.id, amount=Decimal("1200"), status=DepositStatus.PAID
        )
        db.add(dep)
        db.commit()
        _age(db, DepositRecord, dep.id, 2000)

        stats = purge_expired_data(db)
        assert stats.get("deposit_record", 0) == 0
        assert db.query(DepositRecord).count() == 1


class TestVoiceRetention:
    def test_voice_purged_after_6_months(self, db):
        from backend.tasks.scheduler import purge_expired_data

        _, child = _mk_user_child(db)
        old_v = VoiceRecording(
            child_id=child.id,
            book_id=1,
            text_content="hello",
            audio_url="uploads/voice/nonexist.wav",
            duration_seconds=10,
        )
        new_v = VoiceRecording(
            child_id=child.id,
            book_id=1,
            text_content="world",
            audio_url="uploads/voice/new.wav",
            duration_seconds=10,
        )
        db.add_all([old_v, new_v])
        db.commit()
        _age(db, VoiceRecording, old_v.id, 200)  # >6 个月
        _age(db, VoiceRecording, new_v.id, 30)

        stats = purge_expired_data(db)
        assert stats.get("voice_recording") == 1
        assert db.query(VoiceRecording).count() == 1


class TestConsentExempt:
    def test_consent_record_never_purged(self, db):
        from backend.domain.user.consent_model import ConsentRecord
        from backend.tasks.scheduler import purge_expired_data

        user, _ = _mk_user_child(db)
        cr = ConsentRecord(
            user_id=user.id,
            consent_type="privacy_policy",
            consent_version="v1.0",
            consent_text_hash="x" * 64,
        )
        db.add(cr)
        db.commit()
        _age(db, ConsentRecord, cr.id, 3000)  # 8 年多

        purge_expired_data(db)
        assert db.query(ConsentRecord).count() == 1
