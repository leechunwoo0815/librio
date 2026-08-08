# tests/unit/test_f089_damage_list_serializable.py
"""F-089 损坏报告列表序列化 500 回归测试

根因：get_list 返回 ORM 对象列表，经 AdminActionResponse 序列化抛
PydanticSerializationError → 管理端列表功能损坏。
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.database import Base
from backend.domain.admin.admin_schemas import AdminActionResponse
from backend.domain.admin.services.damage_admin_service import DamageAdminService
from backend.domain.book.damage_model import BookDamageReport
from backend.domain.borrow.models import BorrowRecord
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


def _mk_report(db):
    user = User(openid="f089user", phone="13800008901")
    db.add(user)
    db.commit()
    child = Child(user_id=user.id, name="F089", age=7, grade="二年级")
    db.add(child)
    db.flush()
    br = BorrowRecord(
        child_id=child.id,
        book_id=1,
        borrow_time=datetime.now() - timedelta(days=3),
        due_date=datetime.now() - timedelta(days=1),
        status=0,
    )
    db.add(br)
    db.flush()
    report = BookDamageReport(
        child_id=child.id,
        borrow_record_id=br.id,
        damage_level=2,
        fine_amount=Decimal("100"),
        status=BookDamageReport.STATUS_PENDING_REVIEW,
        description="F089 序列化测试",
    )
    db.add(report)
    db.commit()
    return report


class TestF089DamageListSerializable:
    def test_get_list_response_serializable(self, db):
        _mk_report(db)
        result = DamageAdminService(db).get_list()
        assert result["total"] == 1

        # 模拟 FastAPI 响应序列化——修复前抛 PydanticSerializationError
        from fastapi.encoders import jsonable_encoder

        encoded = jsonable_encoder(AdminActionResponse(data=result))
        items = encoded["data"]["items"]
        assert isinstance(items, list)
        assert all(isinstance(i, dict) for i in items)
        assert items[0]["fine_amount"] == "100.00"
        assert items[0]["damage_level"] == 2
