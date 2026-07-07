# backend/tasks/jobs/member_expiry.py
"""会员到期检测定时任务"""

import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


def check():
    """会员到期提醒：提前30/15/7/3/2/1天通知"""
    from backend.database import get_session
    from backend.domain.child.models import Child
    from backend.common.types import MemberStatus
    from backend.domain.message.models import SystemMessage

    db = get_session()
    try:
        today = date.today()
        notify_days = [30, 15, 7, 3, 2, 1]

        for days in notify_days:
            target_date = today + timedelta(days=days)
            children = (
                db.query(Child)
                .filter(
                    Child.status == MemberStatus.OFFICIAL,
                    Child.member_expire_time.isnot(None),
                    Child.is_deleted == 0,
                )
                .all()
            )

            for child in children:
                if (
                    child.member_expire_time
                    and child.member_expire_time.date() == target_date
                ):
                    db.add(
                        SystemMessage(
                            user_id=child.user_id,
                            title="会员续费提醒",
                            content=f"您的孩子 {child.name} 的正式会员将在{days}天后（{target_date}）到期，请及时续费。",
                            msg_type=5,
                            priority=1 if days <= 3 else 0,
                        )
                    )
                    logger.info(
                        f"MEMBER_EXPIRY: child={child.id}, name={child.name}, "
                        f"expires={target_date}, days_left={days}"
                    )
        db.commit()
        logger.info("Member expiry check completed")
    except Exception as e:
        db.rollback()
        logger.error(f"Member expiry check failed: {e}", exc_info=True)
    finally:
        db.close()


def check_grace_period():
    """缓冲期关停：到期超15天自动标记为已过期"""
    from backend.database import get_session
    from backend.domain.child.models import Child
    from backend.common.types import MemberStatus

    db = get_session()
    try:
        cutoff = datetime.now() - timedelta(days=15)
        expired = (
            db.query(Child)
            .filter(
                Child.status == MemberStatus.OFFICIAL,
                Child.member_expire_time.isnot(None),
                Child.member_expire_time < cutoff,
                Child.is_deleted == 0,
            )
            .all()
        )

        for child in expired:
            child.status = MemberStatus.EXPIRED
            logger.info(f"GRACE_SHUTDOWN: child={child.id}, name={child.name}")

        if expired:
            db.commit()
            logger.info(f"Grace period shutdown: {len(expired)} children expired")
    except Exception as e:
        db.rollback()
        logger.error(f"Grace period shutdown failed: {e}", exc_info=True)
    finally:
        db.close()
