# tests/unit/test_f078_transfer_reject_lock.py
"""F-078 终审闭环：reject 与 approve 对称行锁回归测试

根因（复审 P1）：approve 有 with_for_update（L92），reject（L113-137）无锁——
并发 approve+reject 可致"权益已实际转移（source.status=EXPIRED）但申请终态
REJECTED"，资金/权益口径不一致。上一轮整改声明"已被 F-080 覆盖"系跨域误判
（F-080 的 _get_report_or_raise 属 DamageAdminService，与权益转移无关）。

本文件三测试：
1. test_reject_query_uses_row_lock——结构守护：reject 查询链必须调用
   with_for_update（撤锁必红，SQLite 也有效——直接断言锁 API 调用点）
2. test_reject_after_approve_blocked——行为守卫：approve 后 reject 被拦截
3. test_approve_after_reject_blocked——行为守卫：reject 后 approve 被拦截
并发串行化由 scripts/verify_mysql_concurrency.py 场景 J 实证（权威验收）。
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.domain.message.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
from backend.common.exceptions import ValidationError
from backend.common.types import MemberStatus
from backend.database import Base
from backend.domain.admin.services.benefit_transfer_service import (
    BenefitTransferAdminService,
)
from backend.domain.child.benefit_transfer_model import BenefitTransferApplication
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


def _mk_transfer_app(db):
    """构造 1 个 PENDING 权益转让申请（源会员/目标试读，合法可审）"""
    user = User(openid="f078user", phone="13800007801")
    db.add(user)
    db.commit()
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
    db.add_all([source, target])
    db.commit()
    app = BenefitTransferApplication(
        source_child_id=source.id,
        target_child_id=target.id,
        user_id=user.id,
        status=0,
    )
    db.add(app)
    db.commit()
    return source, target, app


class _LockSpy:
    """记录查询链是否调用 with_for_update（其余调用转发真实 Query）"""

    def __init__(self, query, calls):
        self._query = query
        self._calls = calls

    def filter(self, *args, **kwargs):
        return _LockSpy(self._query.filter(*args, **kwargs), self._calls)

    def with_for_update(self, *args, **kwargs):
        self._calls.append("with_for_update")
        return _LockSpy(self._query.with_for_update(*args, **kwargs), self._calls)

    def first(self, *args, **kwargs):
        return self._query.first(*args, **kwargs)


class TestF078RejectRowLock:
    def test_reject_query_uses_row_lock(self, db, monkeypatch):
        """结构守护：reject 的申请查询必须带 with_for_update（与 approve 对称，撤锁必红）"""
        calls = []
        real_query = db.query

        def spy_query(entity, *args, **kwargs):
            return _LockSpy(real_query(entity, *args, **kwargs), calls)

        monkeypatch.setattr(db, "query", spy_query)
        # 不存在 id 触发查询链（filter→first 前应有 with_for_update）
        with pytest.raises(ValidationError, match="申请不存在"):
            BenefitTransferAdminService(db).reject(999999, reviewer_id=1)
        assert "with_for_update" in calls, (
            "reject 查询未带行锁——并发 approve+reject 可覆盖终态（撤锁必红）"
        )

    def test_reject_after_approve_blocked(self, db):
        """行为守卫：approve 已转移权益并置 1 → reject 必须被拦截"""
        source, target, app = _mk_transfer_app(db)
        svc = BenefitTransferAdminService(db)
        result = svc.approve(app.id, reviewer_id=1, review_remark="ok")
        assert result["success"] is True
        with pytest.raises(ValidationError, match="已处理"):
            svc.reject(app.id, reviewer_id=2, review_remark="迟到的拒绝")
        db.refresh(app)
        assert app.status == 1  # 不被 reject 覆盖
        db.refresh(source)
        assert source.status == MemberStatus.EXPIRED  # 权益转移保持

    def test_approve_after_reject_blocked(self, db):
        """行为守卫：reject 置 2 → approve 必须被拦截（不得再转移权益）"""
        source, target, app = _mk_transfer_app(db)
        svc = BenefitTransferAdminService(db)
        result = svc.reject(app.id, reviewer_id=2, review_remark="no")
        assert result["success"] is True
        with pytest.raises(ValidationError, match="已处理"):
            svc.approve(app.id, reviewer_id=1, review_remark="迟到的通过")
        db.refresh(app)
        assert app.status == 2
        db.refresh(source)
        assert source.status == MemberStatus.OFFICIAL  # 未发生转移
