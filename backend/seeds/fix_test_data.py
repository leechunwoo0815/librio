#!/usr/bin/env python3
"""
修复测试数据：把 58 个孩子从单一用户分散到多个用户，补充活动和报名数据。
幂等执行，不会破坏已有业务数据。
"""

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime, timedelta
from backend.database import _get_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from backend.domain.user.models import User
from backend.domain.child.models import Child
from backend.domain.activity.models import Activity, ActivityEnrollment
from backend.domain.reservation.models import Reservation
from backend.domain.book.models import Book
from backend.domain.admin.models import Teacher, TeacherSchedule, Venue
from backend.common.types import ReservationStatus

logger = logging.getLogger(__name__)


def fix_data():
    engine = _get_engine()
    Session = sessionmaker(bind=engine)
    db = Session()

    logger.info("🔧 开始修复测试数据...")

    # 1. 找到已有业务数据的孩子（不能删除/不能改 user_id 也不安全，保留）
    used_rows = db.execute(
        text("""
        SELECT DISTINCT child_id FROM (
            SELECT child_id FROM borrow_record WHERE is_deleted=0
            UNION
            SELECT child_id FROM `order` WHERE is_deleted=0 AND child_id IS NOT NULL
            UNION
            SELECT child_id FROM activity_enrollment WHERE is_deleted=0
            UNION
            SELECT child_id FROM reading_submission WHERE is_deleted=0
            UNION
            SELECT child_id FROM reading_progress
            UNION
            SELECT child_id FROM bookshelf WHERE is_deleted=0
        ) t
    """)
    ).fetchall()
    used_child_ids = {r[0] for r in used_rows}
    logger.info(f"  已有业务关联的孩子: {len(used_child_ids)} 个")

    all_children = (
        db.query(Child).filter(Child.is_deleted == 0).order_by(Child.id).all()
    )
    free_children = [c for c in all_children if c.id not in used_child_ids]
    logger.info(f"  自由孩子: {len(free_children)} 个")

    # 2. 创建 10 个测试家长用户
    new_users = []
    sample_users = [
        ("13900000001", "张女士"),
        ("13900000002", "李先生"),
        ("13900000003", "王女士"),
        ("13900000004", "赵先生"),
        ("13900000005", "刘女士"),
        ("13900000006", "陈先生"),
        ("13900000007", "杨女士"),
        ("13900000008", "周先生"),
        ("13900000009", "吴先生"),
        ("13900000010", "郑女士"),
    ]
    for phone, parent_name in sample_users:
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            user = User(
                openid=f"test_openid_{phone[-4:]}", phone=phone, parent_name=parent_name
            )
            db.add(user)
            db.flush()
        new_users.append(user)
    logger.info(f"  ✅ 测试家长用户: {len(new_users)} 个")

    # 3. 给每个新用户分配 3 个孩子（保留 2 个给原用户作为多孩示例）
    kept_for_original = 2
    needed = len(new_users) * 3 + kept_for_original
    if len(free_children) < needed:
        needed = len(free_children)
        kept_for_original = 0

    assignments = []
    idx = 0
    for u in new_users:
        for _ in range(3):
            if idx >= needed - kept_for_original:
                break
            assignments.append((u.id, free_children[idx]))
            idx += 1

    for user_id, child in assignments:
        child.user_id = user_id
        # 给每个孩子起个不太重复的名字
        if child.name in ("测试小朋友", "正式测试孩子") or child.name is None:
            child.name = random_child_name(child.id)
        child.status = Child.STATUS_OFFICIAL
        db.add(child)
    db.flush()
    logger.info(f"  ✅ 已分配 {len(assignments)} 个孩子到新用户")

    # 原用户保留 2 个自由孩子（多孩家庭示例）
    original_user = db.query(User).order_by(User.id).first()
    remaining_free = [
        c
        for c in free_children
        if c.user_id == original_user.id and c.id not in used_child_ids
    ]
    for i, child in enumerate(remaining_free[:kept_for_original]):
        if child.name in ("测试小朋友", "正式测试孩子") or child.name is None:
            child.name = random_child_name(child.id)
        child.status = Child.STATUS_OFFICIAL
        db.add(child)
    if kept_for_original:
        logger.info(f"  ✅ 原用户保留 {kept_for_original} 个孩子作为多孩示例")

    # 4. 软删除多余自由孩子
    to_delete = [
        c
        for c in free_children
        if c.user_id == original_user.id and c.id not in used_child_ids
    ]
    # 保留已分配的 + kept_for_original
    assigned_ids = {c.id for _, c in assignments}
    deleted_count = 0
    for c in to_delete:
        if c.id in assigned_ids:
            continue
        if kept_for_original > 0 and c.id in {
            cc.id for cc in remaining_free[:kept_for_original]
        }:
            continue
        c.is_deleted = 1
        db.add(c)
        deleted_count += 1
    logger.info(f"  ✅ 软删除多余孩子: {deleted_count} 个")

    # 5. 确保有 enrolling 状态的活动，并给活动添加报名
    now = datetime.now()
    activity = (
        db.query(Activity)
        .filter(Activity.status == Activity.STATUS_ENROLLING, Activity.is_deleted == 0)
        .first()
    )
    if not activity:
        activity = Activity(
            title="周末绘本阅读沙龙",
            description="本周绘本阅读与分享活动",
            type=Activity.TYPE_READING,
            status=Activity.STATUS_ENROLLING,
            start_time=now + timedelta(days=3),
            end_time=now + timedelta(days=3, hours=2),
            enroll_deadline=now + timedelta(days=2),
            max_participants=20,
            location="朝阳馆",
            is_free=1,
        )
        db.add(activity)
        db.flush()
        logger.info(f"  ✅ 创建可报名活动: {activity.title}")

    # 给活动添加 5 条已报名记录
    enrolled_child_ids = {
        e.child_id
        for e in db.query(ActivityEnrollment)
        .filter(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.is_deleted == 0,
        )
        .all()
    }
    available_children = (
        db.query(Child)
        .filter(Child.is_deleted == 0, ~Child.id.in_(list(enrolled_child_ids) or [0]))
        .limit(10)
        .all()
    )
    added = 0
    for child in available_children[:5]:
        ticket = f"ACT{child.id:05d}"
        existing = (
            db.query(ActivityEnrollment)
            .filter(
                ActivityEnrollment.activity_id == activity.id,
                ActivityEnrollment.child_id == child.id,
                ActivityEnrollment.is_deleted == 0,
            )
            .first()
        )
        if not existing:
            db.add(
                ActivityEnrollment(
                    activity_id=activity.id,
                    child_id=child.id,
                    ticket_code=ticket,
                    status=ActivityEnrollment.STATUS_APPROVED,
                )
            )
            added += 1
    activity.current_participants = added + len(enrolled_child_ids)
    db.add(activity)
    logger.info(f"  ✅ 活动报名记录: 新增 {added} 条")

    # 6. 补充有效预约（便于测试确认取书/取消）
    active_count = (
        db.query(Reservation)
        .filter(
            Reservation.status == ReservationStatus.PENDING,
            Reservation.is_deleted == 0,
        )
        .count()
    )
    if active_count < 3:
        books = db.query(Book).filter(Book.is_deleted == 0).limit(5).all()
        children_for_resv = (
            db.query(Child)
            .filter(
                Child.is_deleted == 0,
                ~Child.id.in_(list(enrolled_child_ids) or [0]),
            )
            .limit(5)
            .all()
        )
        for i, child in enumerate(children_for_resv[:3]):
            existing = (
                db.query(Reservation)
                .filter(
                    Reservation.child_id == child.id,
                    Reservation.status == ReservationStatus.PENDING,
                    Reservation.is_deleted == 0,
                )
                .first()
            )
            if existing:
                continue
            book = books[i % len(books)] if books else None
            if not book:
                continue
            db.add(
                Reservation(
                    child_id=child.id,
                    book_id=book.id,
                    status=ReservationStatus.PENDING,
                    expire_time=now + timedelta(days=3),
                )
            )
            active_count += 1
        logger.info(f"  ✅ 有效预约: {active_count} 条")

    # 7. 给老师分配孩子和排班，让“服务学员/课表”有数据
    teachers = db.query(Teacher).filter(Teacher.is_deleted == 0).all()
    children_for_teachers = (
        db.query(Child)
        .filter(Child.is_deleted == 0, Child.teacher_id.is_(None))
        .limit(len(teachers) * 3)
        .all()
    )
    for i, teacher in enumerate(teachers):
        # 分配 2-3 个孩子
        assigned = children_for_teachers[i * 3 : (i + 1) * 3]
        for child in assigned:
            child.teacher_id = teacher.id
        # 创建两条排班
        existing_schedules = (
            db.query(TeacherSchedule)
            .filter(TeacherSchedule.teacher_id == teacher.id)
            .count()
        )
        if existing_schedules == 0:
            db.add(
                TeacherSchedule(
                    teacher_id=teacher.id,
                    weekday=(i % 5) + 1,
                    start_time="09:00",
                    end_time="12:00",
                )
            )
            db.add(
                TeacherSchedule(
                    teacher_id=teacher.id,
                    weekday=(i % 5) + 3,
                    start_time="14:00",
                    end_time="17:00",
                )
            )
    logger.info(f"  ✅ 老师: 为 {len(teachers)} 位老师分配孩子和排班")

    # 8. 给没有分配场馆的孩子分配场馆
    children_no_venue = (
        db.query(Child).filter(Child.is_deleted == 0, Child.venue_id.is_(None)).all()
    )
    if children_no_venue:
        venues = db.query(Venue).filter(Venue.is_deleted == 0).all()
        for i, child in enumerate(children_no_venue):
            child.venue_id = venues[i % len(venues)].id if venues else None
        logger.info(
            f"  ✅ 场馆: 为 {len(children_no_venue)} 个孩子分配场馆 (共 {len(venues)} 个场馆)"
        )
    else:
        logger.info("  ✅ 场馆: 所有孩子已有场馆，跳过")

    db.commit()
    logger.info("\n🎉 测试数据修复完成")

    # 统计
    user_count = db.query(User).filter(User.is_deleted == 0).count()
    child_count = db.query(Child).filter(Child.is_deleted == 0).count()
    logger.info(f"   用户: {user_count}，孩子: {child_count}")
    db.close()


def random_child_name(seed_id: int) -> str:
    names = [
        "艾米",
        "鲍勃",
        "查理",
        "黛西",
        "艾拉",
        "菲利克斯",
        "格蕾丝",
        "亨利",
        "伊娃",
        "杰克",
        "凯莉",
        "利奥",
        "玛雅",
        "诺亚",
        "奥利维亚",
        "彼得",
        "昆西",
        "露西",
        "山姆",
        "蒂娜",
        "维克多",
        "温迪",
        "赞恩",
        "佐伊",
    ]
    return names[(seed_id - 1) % len(names)]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fix_data()
