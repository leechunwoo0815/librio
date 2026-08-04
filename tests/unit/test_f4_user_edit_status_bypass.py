# tests/unit/test_f4_user_edit_status_bypass.py
"""F4 回归测试：管理端编辑用户不得再直写孩子状态（后门已移除）

此前 UpdateUserRequest.child_status 可绕过状态机直接改第一个孩子状态：
不校验迁移、不写 exited_at（破坏 H5 计时）、不写 member_expire_time（永久观察期）、
多孩家庭只改 id 最小的孩子。修复后 child_status 被 extra=forbid 拒绝，
孩子状态变更一律走 PUT /child/{id}/status 状态机。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.bootstrap import register_event_handlers
from backend.common.types import MemberStatus
from backend.database import Base
from backend.domain.admin.admin_schemas import UpdateUserRequest
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


def _mk_user_with_child(db, status=MemberStatus.OFFICIAL):
    user = User(openid="f4user", phone="13800006666")
    db.add(user)
    db.commit()
    child = Child(
        user_id=user.id,
        name="F4",
        age=7,
        grade="二年级",
        status=status,
    )
    db.add(child)
    db.commit()
    return user, child


class TestUpdateUserNoChildStatus:
    def test_schema_rejects_child_status(self):
        """child_status 字段已移除，提交即 422（extra=forbid）"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UpdateUserRequest(parent_name="新名字", child_status=4)

    def test_update_user_does_not_touch_child_status(self, db):
        """编辑家长信息不改变孩子状态（后门消失）"""
        from backend.domain.admin.services.user_service import AdminUserService

        user, child = _mk_user_with_child(db)
        AdminUserService(db).update_user(user.id, UpdateUserRequest(parent_name="改名"))
        db.refresh(child)
        assert child.status == MemberStatus.OFFICIAL  # 状态保持不变
