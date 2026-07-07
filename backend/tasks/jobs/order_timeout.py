# backend/tasks/jobs/order_timeout.py
"""订单超时关闭定时任务"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def close_expired():
    """关闭超时未支付订单（下单后30分钟）"""
    from backend.database import get_session
    from backend.domain.order.models import Order
    from backend.common.types import PayStatus

    db = get_session()
    try:
        cutoff = datetime.now() - timedelta(minutes=30)
        expired = (
            db.query(Order)
            .filter(
                Order.pay_status == PayStatus.PENDING,
                Order.create_time < cutoff,
                Order.is_deleted == 0,
            )
            .all()
        )

        for order in expired:
            order.pay_status = PayStatus.CLOSED
            logger.info(f"ORDER_CLOSED: {order.order_no}, created={order.create_time}")

        if expired:
            db.commit()
            logger.info(f"Expired orders closed: {len(expired)}")
        logger.info("Order timeout check completed")
    except Exception as e:
        db.rollback()
        logger.error(f"Order timeout check failed: {e}", exc_info=True)
    finally:
        db.close()
