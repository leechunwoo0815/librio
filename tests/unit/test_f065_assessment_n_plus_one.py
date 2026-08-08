"""F-065 回归：assessment 管理端列表不得逐条查询 Child/Teacher/Venue（N+1）

R15 报告定位 list_assessments 分页循环内 3 次逐条查询；修复为 in_ 批量预取后，
本测试用 SQL 计数守护（expunge_all 防 identity map 缓存假绿）。
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import backend.domain.admin.models  # noqa: F401
from backend.database import Base
from backend.domain.admin.models import Teacher, Venue
from backend.domain.assessment.models import Assessment
from backend.domain.assessment.service import AssessmentService
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


def _seed(db):
    user = User(openid="f065", phone="13800065001")
    db.add(user)
    db.flush()
    children = []
    for i in range(3):
        c = Child(user_id=user.id, name=f"评估孩{i}", age=5 + i, grade="大班")
        db.add(c)
        db.flush()
        children.append(c)
    venue = Venue(name="评估馆", address="测试路1号", phone="13800065003")
    db.add(venue)
    db.flush()
    teacher = Teacher(name="评估老师", phone="13800065002", venue_id=venue.id)
    db.add(teacher)
    db.flush()
    for i, c in enumerate(children):
        db.add(
            Assessment(
                child_id=c.id,
                teacher_id=teacher.id,
                venue_id=venue.id,
                status="completed",
                comprehension_score=80 + i,
                ar_level_before=1,
                ar_level_after=2,
                scheduled_date=datetime.now(),
                completed_date=datetime.now(),
            )
        )
    db.commit()
    return children, teacher, venue


def test_list_assessments_no_n_plus_one(db):
    children, teacher, venue = _seed(db)
    db.expunge_all()  # 防 identity map 缓存掩盖懒加载

    lazy_sql = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        import re

        text = str(statement)
        if (
            text.upper().startswith("SELECT")
            and re.search(r"\bFROM\s+(child|teacher|venue)\b", text, re.IGNORECASE)
            and " JOIN " not in text.upper()
            and " IN (" not in text.upper()  # in_ 批量预取合法，N+1 指逐条 = ?
        ):
            lazy_sql.append(text)

    event.listen(db.get_bind(), "before_cursor_execute", _count)
    try:
        result = AssessmentService(db).list_assessments(page=1, page_size=20)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", _count)

    assert result.total == 3
    assert len(result.items) == 3
    assert lazy_sql == [], f"F-065 N+1 泄漏: {lazy_sql}"
    assert all(i.child_name and i.teacher_name and i.venue_name for i in result.items)
