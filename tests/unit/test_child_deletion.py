# tests/unit/test_child_deletion.py
"""P0-3 儿童数据删除权级联删除 — 单元测试

覆盖：前置校验三场景 / 请求与冷静期取消 / 到期执行级联核验 / withdraw 联动
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.types import BorrowStatus, DepositStatus
from backend.database import Base
from backend.domain.child.deletion_service import (
    DELETE_TABLES_BY_CHILD,
    ChildDeletionService,
)
from backend.domain.child.models import Child
from backend.domain.user.consent_service import ConsentService
from backend.domain.user.models import User


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def user(db):
    u = User(openid=f"test_openid_{uuid.uuid4().hex[:8]}", parent_name="测试家长")
    db.add(u)
    db.flush()
    db.refresh(u)
    return u


def _make_child(db, user, name="测试孩子"):
    c = Child(user_id=user.id, name=name, age=5, grade="中班")
    db.add(c)
    db.flush()
    db.refresh(c)
    return c


def _make_borrow(db, child_id, status, borrow_id=None):
    from backend.domain.borrow.models import BorrowRecord

    rec = BorrowRecord(
        child_id=child_id,
        book_id=1,
        status=status,
        borrow_time=datetime.now() - timedelta(days=5),
        due_date=datetime.now() + timedelta(days=16),
    )
    db.add(rec)
    db.flush()
    return rec


# ── 前置校验 ──


class TestDeletionBlockers:
    def test_blocked_by_active_borrow(self, db, user):
        child = _make_child(db, user)
        _make_borrow(db, child.id, BorrowStatus.BORROWING)
        svc = ChildDeletionService(db)
        blockers = svc.check_deletion_blockers(child.id)
        assert any("未归还" in b for b in blockers)
        with pytest.raises(ValidationError, match="未归还"):
            svc.request_deletion(user.id, child.id)

    def test_blocked_by_overdue_borrow(self, db, user):
        child = _make_child(db, user)
        _make_borrow(db, child.id, BorrowStatus.OVERDUE)
        blockers = ChildDeletionService(db).check_deletion_blockers(child.id)
        assert any("未归还" in b for b in blockers)

    def test_blocked_by_paid_deposit(self, db, user):
        child = _make_child(db, user)
        child.deposit_status = DepositStatus.PAID
        db.flush()
        blockers = ChildDeletionService(db).check_deletion_blockers(child.id)
        assert any("押金" in b for b in blockers)
        with pytest.raises(ValidationError, match="押金"):
            ChildDeletionService(db).request_deletion(user.id, child.id)

    def test_blocked_by_pending_refund(self, db, user):
        from backend.domain.refund.models import RefundApplication

        child = _make_child(db, user)
        db.add(
            RefundApplication(
                order_id=1,
                child_id=child.id,
                user_id=user.id,
                refund_amount=100,
                status=RefundApplication.STATUS_PENDING,
            )
        )
        db.flush()
        blockers = ChildDeletionService(db).check_deletion_blockers(child.id)
        assert any("退款" in b for b in blockers)

    def test_no_blockers_when_returned_and_unpaid(self, db, user):
        child = _make_child(db, user)
        _make_borrow(db, child.id, BorrowStatus.RETURNED)
        assert ChildDeletionService(db).check_deletion_blockers(child.id) == []


# ── 请求与取消 ──


class TestRequestAndCancel:
    def test_request_marks_soft_delete_and_grace(self, db, user):
        child = _make_child(db, user)
        result = ChildDeletionService(db).request_deletion(user.id, child.id)
        assert result["success"] is True
        db.refresh(child)
        assert child.is_deleted == 1
        assert child.deletion_requested_at is not None

    def test_request_wrong_user_404(self, db, user):
        child = _make_child(db, user)
        with pytest.raises(NotFoundError):
            ChildDeletionService(db).request_deletion(user.id + 999, child.id)

    def test_cancel_restores_child(self, db, user):
        child = _make_child(db, user)
        svc = ChildDeletionService(db)
        svc.request_deletion(user.id, child.id)
        result = svc.cancel_deletion(user.id, child.id)
        assert result["success"] is True
        db.refresh(child)
        assert child.is_deleted == 0
        assert child.deletion_requested_at is None

    def test_cancel_without_request_404(self, db, user):
        child = _make_child(db, user)
        with pytest.raises(NotFoundError):
            ChildDeletionService(db).cancel_deletion(user.id, child.id)


# ── 到期执行 ──


class TestExecuteDueDeletions:
    def _seed_related_rows(self, db, child, user):
        from backend.domain.advancement.models import Quiz, QuizAnswer
        from backend.domain.bookshelf.models import Bookshelf, Favorites
        from backend.domain.message.models import MessageReadStatus, SystemMessage
        from backend.domain.reading.models import CheckIn
        from backend.domain.voice.models import VoiceRecording

        db.add(CheckIn(child_id=child.id, check_type=1, check_date=datetime.now()))
        db.add(
            VoiceRecording(
                child_id=child.id,
                book_id=1,
                text_content="hello world",
                audio_url="/uploads/voice/deletion_test.mp3",
                duration_seconds=5,
            )
        )
        db.add(Bookshelf(child_id=child.id, book_id=1))
        db.add(Favorites(child_id=child.id, book_id=1))
        quiz = Quiz(child_id=child.id, book_id=1)
        db.add(quiz)
        db.flush()
        db.add(
            QuizAnswer(
                quiz_id=quiz.id, question_id=1, selected_answer="A", is_correct=1
            )
        )
        msg = SystemMessage(user_id=user.id, msg_type=1, title="t", content="c")
        db.add(msg)
        db.flush()
        db.add(MessageReadStatus(message_id=msg.id, user_id=user.id))
        # 财务数据：应保留
        _make_borrow(db, child.id, BorrowStatus.RETURNED)
        db.flush()

    def test_not_due_within_grace(self, db, user):
        child = _make_child(db, user)
        ChildDeletionService(db).request_deletion(user.id, child.id)
        result = ChildDeletionService(db).execute_due_deletions()
        assert result["due"] == 0

    def test_execute_cascades_and_retains_financial(self, db, user, tmp_path):
        from backend.domain.borrow.models import BorrowRecord
        from backend.domain.message.models import MessageReadStatus
        from backend.domain.reading.models import CheckIn
        from backend.domain.voice.models import VoiceRecording

        child = _make_child(db, user)
        self._seed_related_rows(db, child, user)

        # 语音文件：放到 uploads/voice/ 下（服务执行后应被删除）
        from backend.domain.child import deletion_service as ds_module

        voice_dir = ds_module.UPLOADS_DIR / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        voice_file = voice_dir / "deletion_test.mp3"
        voice_file.write_bytes(b"fake-audio")

        # 直接置为已过冷静期
        child.is_deleted = 1
        child.deletion_requested_at = datetime.now() - timedelta(hours=25)
        db.flush()

        result = ChildDeletionService(db).execute_due_deletions()
        assert result["due"] == 1
        assert result["executed"] == 1

        # 非财务数据已物理删除
        assert db.query(CheckIn).filter_by(child_id=child.id).count() == 0
        assert db.query(VoiceRecording).filter_by(child_id=child.id).count() == 0
        assert db.query(MessageReadStatus).filter_by(user_id=user.id).count() == 0
        from backend.domain.advancement.models import Quiz, QuizAnswer

        assert db.query(Quiz).filter_by(child_id=child.id).count() == 0
        assert db.query(QuizAnswer).count() == 0
        # 财务数据保留
        assert db.query(BorrowRecord).filter_by(child_id=child.id).count() == 1
        # 语音文件已删
        assert not voice_file.exists()
        # 冷静期标记已清除，child 行保留（软删除状态）
        db.refresh(child)
        assert child.deletion_requested_at is None
        assert child.is_deleted == 1

    def test_delete_table_list_covers_metadata(self):
        """DELETE_TABLES_BY_CHILD 中的表必须真实存在于 metadata（防表名漂移）"""
        for table_name in DELETE_TABLES_BY_CHILD:
            assert table_name in Base.metadata.tables, f"表不存在: {table_name}"


# ── withdraw(child_data) 联动 ──


class TestWithdrawCascade:
    def test_withdraw_child_data_triggers_deletion(self, db, user):
        child = _make_child(db, user)
        svc = ConsentService(db)
        svc.grant_consent(user.id, "child_data")
        resp = svc.withdraw_consent(user.id, "child_data")
        assert resp.withdrawn_at is not None
        db.refresh(child)
        assert child.is_deleted == 1
        assert child.deletion_requested_at is not None

    def test_withdraw_child_data_blocked_by_active_borrow(self, db, user):
        child = _make_child(db, user)
        _make_borrow(db, child.id, BorrowStatus.BORROWING)
        svc = ConsentService(db)
        svc.grant_consent(user.id, "child_data")
        with pytest.raises(ValidationError, match="未归还"):
            svc.withdraw_consent(user.id, "child_data")
        # 拒绝后同意仍有效、孩子未受影响
        assert svc.has_valid_consent(user.id, "child_data")
        db.refresh(child)
        assert child.is_deleted == 0

    def test_withdraw_child_data_no_children(self, db, user):
        """无孩子时撤回：直接标记撤回即可"""
        svc = ConsentService(db)
        svc.grant_consent(user.id, "child_data")
        resp = svc.withdraw_consent(user.id, "child_data")
        assert resp.withdrawn_at is not None
