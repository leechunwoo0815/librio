# tests/unit/test_user_list_child_status_filter.py
"""P3：管理端用户列表 child_status 筛选（此前前端传参被后端忽略——"筛选摆设"）"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.admin.services.user_service import AdminUserService
from backend.domain.child.models import Child
from backend.domain.user.models import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mk(db, status, name):
    u = User(
        openid=f"uf_{uuid.uuid4().hex[:8]}",
        parent_name=name,
        phone=f"137{uuid.uuid4().int % 100000000:08d}",
    )
    db.add(u)
    db.flush()
    c = Child(user_id=u.id, name=f"孩{name}", age=7, grade="一年级", status=status)
    db.add(c)
    db.commit()
    return u


class TestChildStatusFilter:
    def test_filter_by_official(self, db):
        """child_status=2（OFFICIAL）→ 只返回正式会员孩子所属用户"""
        a = _mk(db, 2, "甲")
        _mk(db, 0, "乙")
        result = AdminUserService(db).list_users_with_children(
            page=1, page_size=20, child_status=2
        )
        ids = [u["id"] for u in result["items"]]
        assert a.id in ids
        assert len(ids) == 1

    def test_filter_by_trial(self, db):
        """child_status=0（TRIAL）→ 只返回体验用户"""
        _mk(db, 2, "甲")
        b = _mk(db, 0, "乙")
        result = AdminUserService(db).list_users_with_children(
            page=1, page_size=20, child_status=0
        )
        ids = [u["id"] for u in result["items"]]
        assert b.id in ids
        assert len(ids) == 1

    def test_no_filter_returns_all(self, db):
        """child_status=None → 全部返回（默认行为不变）"""
        a = _mk(db, 2, "甲")
        b = _mk(db, 0, "乙")
        result = AdminUserService(db).list_users_with_children(page=1, page_size=20)
        ids = [u["id"] for u in result["items"]]
        assert a.id in ids and b.id in ids
