# tests/unit/test_teacher_service.py
"""
[What] 老师服务单元测试
[Why] TDD: 验证老师管理和孩子分配逻辑
[How] 使用SQLite内存数据库
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.admin.models import Teacher, TeacherSchedule
from backend.domain.admin.services.teacher_service import AdminTeacherService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_test_data(db):
    user = User(openid="test_teacher_user", phone="13800138002")
    db.add(user)
    db.commit()

    child = Child(user_id=user.id, name="小明", age=7, grade="二年级", status=Child.STATUS_OFFICIAL)
    db.add(child)
    db.commit()

    teacher = Teacher(name="王老师", phone="13900139000", venue_id=1,
                      introduction="10年英文教学经验", expertise="初级阅读指导")
    db.add(teacher)
    db.commit()

    return user, child, teacher


def test_create_teacher(db):
    """创建老师"""
    svc = AdminTeacherService(db)
    t = svc.create_teacher(name="李老师", phone="13900139001", venue_id=1,
                           introduction="5年经验", expertise="阅读启蒙")
    assert t.id is not None
    assert t.name == "李老师"


def test_assign_teacher_to_child(db):
    """分配老师给孩子"""
    _, child, teacher = _create_test_data(db)
    svc = AdminTeacherService(db)
    result = svc.assign_teacher(child.id, teacher.id)
    assert result is True

    # 验证 child.teacher_id 已更新
    db.refresh(child)
    assert child.teacher_id == teacher.id


def test_get_teacher_children(db):
    """获取老师负责的孩子列表"""
    user, child, teacher = _create_test_data(db)
    svc = AdminTeacherService(db)
    svc.assign_teacher(child.id, teacher.id)

    children = svc.get_teacher_children(teacher.id)
    assert len(children) == 1
    assert children[0].name == "小明"


def test_get_child_teacher(db):
    """获取孩子的老师信息"""
    _, child, teacher = _create_test_data(db)
    svc = AdminTeacherService(db)
    svc.assign_teacher(child.id, teacher.id)

    t = svc.get_child_teacher(child.id)
    assert t is not None
    assert t.name == "王老师"


def test_assign_teacher_not_found(db):
    """分配不存在的老师"""
    _, child, _ = _create_test_data(db)
    svc = AdminTeacherService(db)
    with pytest.raises(Exception, match="老师不存在"):
        svc.assign_teacher(child.id, 9999)


def test_create_schedule(db):
    """创建老师排班"""
    _, _, teacher = _create_test_data(db)
    svc = AdminTeacherService(db)
    schedule = svc.create_schedule(teacher.id, weekday=1, start_time="10:00", end_time="11:00")
    assert schedule.id is not None
    assert schedule.weekday == 1


def test_get_teacher_schedule(db):
    """获取老师排班"""
    _, _, teacher = _create_test_data(db)
    svc = AdminTeacherService(db)
    svc.create_schedule(teacher.id, weekday=1, start_time="10:00", end_time="11:00")
    svc.create_schedule(teacher.id, weekday=3, start_time="14:00", end_time="15:00")

    schedules = svc.get_teacher_schedule(teacher.id)
    assert len(schedules) == 2


def test_get_all_teachers(db):
    """获取所有老师"""
    _create_test_data(db)
    svc = AdminTeacherService(db)
    svc.create_teacher(name="李老师", phone="13900139001", venue_id=1)
    teachers = svc.get_all_teachers()
    assert len(teachers) == 2


def test_reassign_teacher(db):
    """重新分配老师"""
    user, child, teacher1 = _create_test_data(db)
    teacher2 = Teacher(name="李老师", phone="13900139001", venue_id=1)
    db.add(teacher2)
    db.commit()

    svc = AdminTeacherService(db)
    svc.assign_teacher(child.id, teacher1.id)
    svc.assign_teacher(child.id, teacher2.id)

    db.refresh(child)
    assert child.teacher_id == teacher2.id

    # 老师1应该没有孩子了
    children1 = svc.get_teacher_children(teacher1.id)
    assert len(children1) == 0
