# backend/tasks/jobs/reservation_expire.py
"""预约过期检测定时任务"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def check():
    """检查预约过期：标记过期 + 发布事件释放库存"""
    from backend.database import get_session
    from backend.domain.reservation.models import Reservation
    from backend.common.types import ReservationStatus
    from backend.common.events import event_bus, ReservationExpiredEvent

    db = get_session()
    try:
        now = datetime.now()
        expired = (
            db.query(Reservation)
            .filter(
                Reservation.status == ReservationStatus.PENDING,
                Reservation.expire_time < now,
                Reservation.is_deleted == 0,
            )
            .all()
        )

        for r in expired:
            r.status = ReservationStatus.EXPIRED
            event_bus.publish(
                ReservationExpiredEvent(
                    child_id=r.child_id,
                    book_id=r.book_id,
                    reservation_id=r.id,
                ),
                db=db,
            )
            logger.info(
                f"RESERVATION_EXPIRED: id={r.id}, child={r.child_id}, "
                f"book={r.book_id}, expire_time={r.expire_time}"
            )

        if expired:
            db.commit()
            logger.info(f"Reservation expired: {len(expired)} records")
        logger.info("Reservation expire check completed")
    except Exception as e:
        db.rollback()
        logger.error(f"Reservation expire check failed: {e}", exc_info=True)
    finally:
        db.close()
