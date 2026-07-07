# backend/tasks/jobs/activity_status.py
"""活动状态迁移定时任务"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def check():
    """
    [What] 活动状态自动迁移
    [Why] 报名截止/进行中/结束 三个时间点自动切换状态
    [How] 根据当前时间与活动时间比较，自动迁移状态
    """
    from backend.database import get_session
    from backend.domain.activity.models import Activity
    from backend.common.types import ActivityStatus

    db = get_session()
    try:
        now = datetime.now()
        migrated = 0

        # 报名中 → 报名截止
        activities = (
            db.query(Activity)
            .filter(
                Activity.status == ActivityStatus.ENROLLING,
                Activity.enroll_deadline.isnot(None),
                Activity.enroll_deadline < now,
                Activity.is_deleted == 0,
            )
            .all()
        )
        for a in activities:
            a.status = ActivityStatus.ENROLL_CLOSED
            migrated += 1

        # 报名截止 → 进行中
        activities = (
            db.query(Activity)
            .filter(
                Activity.status == ActivityStatus.ENROLL_CLOSED,
                Activity.start_time <= now,
                Activity.is_deleted == 0,
            )
            .all()
        )
        for a in activities:
            a.status = ActivityStatus.IN_PROGRESS
            migrated += 1

        # 进行中 → 已结束
        activities = (
            db.query(Activity)
            .filter(
                Activity.status == ActivityStatus.IN_PROGRESS,
                Activity.end_time < now,
                Activity.is_deleted == 0,
            )
            .all()
        )
        for a in activities:
            a.status = ActivityStatus.FINISHED
            migrated += 1

        if migrated:
            db.commit()
            logger.info(f"Activity status migrated: {migrated} changes")
        logger.info("Activity status check completed")
    except Exception as e:
        db.rollback()
        logger.error(f"Activity status check failed: {e}", exc_info=True)
    finally:
        db.close()
