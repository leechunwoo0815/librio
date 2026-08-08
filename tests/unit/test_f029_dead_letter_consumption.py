"""F-029 回归：死信消费（查询/重放/删除/清扫）

原缺陷：DeadLetterEvent 只写不读——无查询/重放/清扫，retry_count/resolved_at 从未使用。
修复后提供管理端列表/重放/单删/批量清扫；重放复用已注册 handler。
"""

import dataclasses
import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.common.events as events_mod
from backend.common.dead_letter_model import DeadLetterEvent
from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.events import DomainEvent, event_bus
from backend.database import Base
from backend.domain.admin.services.system_service import AdminSystemService


@dataclasses.dataclass
class TestReplayEvent(DomainEvent):
    __test__ = False  # 非测试类，防止 pytest 误收集

    event_type: str = "test.replay"
    child_id: int = 0
    note: str = ""


# 注册到 events 模块（replay 通过 vars(events) 扫描恢复事件类）
events_mod.TestReplayEvent = TestReplayEvent  # type: ignore[attr-defined]


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mk_dead_letter(db, event_type="test.replay", error="boom") -> DeadLetterEvent:
    entry = DeadLetterEvent(
        event_type=event_type,
        event_data=json.dumps(
            {"event_type": event_type, "child_id": 7, "note": "hello"}
        ),
        handler_name="test_handler",
        error_message=error,
        retry_count=0,
    )
    db.add(entry)
    db.commit()
    return entry


class TestListDeadLetters:
    def test_list_paginated(self, db):
        e1 = _mk_dead_letter(db)
        _mk_dead_letter(db)
        result = AdminSystemService(db).list_dead_letters(page=1, page_size=1)
        assert result["total"] == 2
        assert len(result["items"]) == 1
        assert result["has_next"] is True
        assert result["items"][0]["id"] in (e1.id, e1.id + 1)

    def test_filter_resolved(self, db):
        e1 = _mk_dead_letter(db)
        e1.resolved_at = datetime.now()
        db.commit()
        _mk_dead_letter(db)
        svc = AdminSystemService(db)
        unresolved = svc.list_dead_letters(resolved=False)
        resolved = svc.list_dead_letters(resolved=True)
        assert unresolved["total"] == 1
        assert resolved["total"] == 1


class TestReplayDeadLetter:
    def test_replay_success_marks_resolved(self, db):
        received = []

        def _handler(event, session):
            received.append(event)

        event_bus.subscribe("test.replay", _handler)
        try:
            entry = _mk_dead_letter(db)
            result = AdminSystemService(db).replay_dead_letter(entry.id)
        finally:
            event_bus.unsubscribe("test.replay", _handler)

        assert result["success"] is True
        assert len(received) == 1
        assert received[0].child_id == 7
        db.refresh(entry)
        assert entry.resolved_at is not None
        assert entry.retry_count == 1

    def test_replay_failure_keeps_original(self, db):
        def _bad_handler(event, session):
            raise RuntimeError("handler 再次失败")

        event_bus.subscribe("test.replay", _bad_handler)
        try:
            entry = _mk_dead_letter(db)
            with pytest.raises(ValidationError, match="重放失败"):
                AdminSystemService(db).replay_dead_letter(entry.id)
        finally:
            event_bus.unsubscribe("test.replay", _bad_handler)

        db.refresh(entry)
        assert entry.resolved_at is None
        assert entry.retry_count == 0

    def test_replay_unknown_event_type(self, db):
        entry = _mk_dead_letter(db, event_type="ghost.event")
        with pytest.raises(ValidationError, match="未知事件类型"):
            AdminSystemService(db).replay_dead_letter(entry.id)


class TestDeleteAndCleanup:
    def test_delete_single(self, db):
        entry = _mk_dead_letter(db)
        svc = AdminSystemService(db)
        svc.delete_dead_letter(entry.id)
        with pytest.raises(NotFoundError):
            svc.delete_dead_letter(entry.id)

    def test_cleanup_resolved_only(self, db):
        e1 = _mk_dead_letter(db)
        e1.resolved_at = datetime.now()
        db.commit()
        _mk_dead_letter(db)  # 未解决，保留
        result = AdminSystemService(db).cleanup_resolved_dead_letters()
        assert result["message"].startswith("已清理 1")
        remaining = AdminSystemService(db).list_dead_letters()
        assert remaining["total"] == 1
