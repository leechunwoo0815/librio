# tests/unit/test_final_audit_p2.py
"""终审 P2 整改单测 — P2-2 今日全勤 / P2-4 配置范围校验 / P2-8 拍照下沉"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.common.config_audit_model  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.sql_utils import add_with_unique_fallback
from backend.common.types import MemberStatus
from backend.database import Base
from backend.domain.child.models import Child
from backend.domain.message.models import SystemMessage
from backend.domain.reading.models import CheckIn
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


def _mk_child(db, status=MemberStatus.OFFICIAL):
    user = User(openid="p2audit", phone="13800005555")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="P2", age=7, grade="二年级", status=status)
    db.add(child)
    db.commit()
    return user, child


# ---------------------------------------------------------------- P2-2
class TestFullAttendance:
    def _checkin(self, db, child_id, check_type):
        return add_with_unique_fallback(
            db,
            CheckIn(child_id=child_id, check_date=date.today(), check_type=check_type),
        )

    def _full_attendance_msgs(self, db, user_id):
        return (
            db.query(SystemMessage)
            .filter(SystemMessage.user_id == user_id, SystemMessage.title == "今日全勤")
            .count()
        )

    def test_no_message_below_4_types(self, db):
        from backend.domain.reading.service import maybe_send_full_attendance_message

        user, child = _mk_child(db)
        today = date.today()
        for t in (1, 2, 3):
            assert self._checkin(db, child.id, t) is True
            maybe_send_full_attendance_message(db, child.id, today)
        db.commit()
        assert self._full_attendance_msgs(db, user.id) == 0

    def test_message_on_4_types_and_idempotent(self, db):
        from backend.domain.reading.service import maybe_send_full_attendance_message

        user, child = _mk_child(db)
        today = date.today()
        for t in (1, 2, 3, 4):
            assert self._checkin(db, child.id, t) is True
            maybe_send_full_attendance_message(db, child.id, today)
        db.commit()
        assert self._full_attendance_msgs(db, user.id) == 1
        # 重复触发不再发
        maybe_send_full_attendance_message(db, child.id, today)
        db.commit()
        assert self._full_attendance_msgs(db, user.id) == 1


# ---------------------------------------------------------------- P2-4
class TestConfigRangeValidation:
    def test_out_of_range_rejected(self):
        from backend.domain.admin.config_levels import validate_config_value

        assert validate_config_value("borrow_limit", "200") is not None
        assert validate_config_value("borrow_limit", "0") is not None
        assert validate_config_value("observation_days", "731") is not None
        assert validate_config_value("quiz_pass_rate", "1.5") is not None
        assert validate_config_value("review_sla_hours", "0") is not None
        assert validate_config_value("review_sla_hours", "169") is not None

    def test_in_range_accepted(self):
        from backend.domain.admin.config_levels import validate_config_value

        assert validate_config_value("borrow_limit", "10") is None
        assert validate_config_value("observation_days", "45") is None
        assert validate_config_value("quiz_pass_rate", "0.80") is None
        assert validate_config_value("review_sla_hours", "24") is None
        assert validate_config_value("bookshelf_limit", "0") is None  # 0=无限制

    def test_non_numeric_rejected(self):
        from backend.domain.admin.config_levels import validate_config_value

        err = validate_config_value("borrow_limit", "abc")
        assert err is not None and "数值" in err

    def test_unranged_key_passes(self):
        from backend.domain.admin.config_levels import validate_config_value

        assert validate_config_value("venue_name", "任意文本") is None
        assert validate_config_value("unknown_new_key", "999") is None

    def test_all_ranged_keys_exist_in_defaults(self):
        """RANGES 表登记的键必须在 DEFAULTS 中存在（防登记漂移）"""
        from backend.domain.admin.config_levels import CONFIG_RANGES
        from backend.domain.admin.models import SystemConfig

        orphan = set(CONFIG_RANGES) - set(SystemConfig.DEFAULTS)
        assert not orphan, f"RANGES 中存在 DEFAULTS 没有的键: {orphan}"


# ---------------------------------------------------------------- P2-8
class TestCheckoutPhotosService:
    def _mk_borrow(self, db, child_id):
        from backend.domain.borrow.models import BorrowRecord

        record = BorrowRecord(
            child_id=child_id,
            book_id=1,
            borrow_time=datetime.now(),
            due_date=datetime.now() + timedelta(days=21),
            status=0,
        )
        db.add(record)
        db.commit()
        return record

    def test_save_photos(self, db):
        import json

        from backend.domain.admin.services.borrow_service import AdminBorrowService

        _, child = _mk_child(db)
        record = self._mk_borrow(db, child.id)
        svc = AdminBorrowService(db)
        result = svc.save_checkout_photos(record.id, ["front.jpg", "back.jpg"], 1)
        assert result["success"] is True
        db.refresh(record)
        assert json.loads(record.checkout_photos) == ["front.jpg", "back.jpg"]

    def test_not_found_raises(self, db):
        from backend.common.exceptions import NotFoundError
        from backend.domain.admin.services.borrow_service import AdminBorrowService

        svc = AdminBorrowService(db)
        with pytest.raises(NotFoundError):
            svc.save_checkout_photos(99999, ["a.jpg"], 1)
