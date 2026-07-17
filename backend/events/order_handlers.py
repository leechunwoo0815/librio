# backend/events/order_handlers.py
"""订单/押金相关事件处理器"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle_order_paid_for_child(event, db: Session):
    """订单支付 → 更新孩子会员状态（含状态迁移合法性校验）"""
    from datetime import datetime, timedelta
    from backend.common.types import OrderType, MemberStatus
    from backend.domain.child.models import Child
    from backend.common.base_repo import BaseRepository
    from backend.common.config_service import ConfigService

    child_repo = BaseRepository(db, Child)
    child = child_repo.get_by_id(event.child_id)
    if not child:
        logger.warning(f"OrderPaidEvent: child_id={event.child_id} not found")
        return

    if child.status == MemberStatus.EXITED:
        logger.warning(
            f"OrderPaidEvent: child {event.child_id} is EXITED, cannot restore"
        )
        return

    # 合法状态迁移校验
    ALLOWED_TO_OFFICIAL = {
        MemberStatus.OBSERVATION,
        MemberStatus.OFFICIAL,
        MemberStatus.EXPIRED,
    }
    ALLOWED_TO_OBSERVATION = {MemberStatus.TRIAL}

    now = datetime.now()

    if event.order_type in (
        OrderType.OFFICIAL_MEMBER,
        OrderType.QUARTERLY,
        OrderType.SEMI_ANNUAL,
    ):
        if child.status not in ALLOWED_TO_OFFICIAL:
            logger.warning(
                f"OrderPaidEvent: child {event.child_id} status={child.status} "
                f"not allowed to become OFFICIAL"
            )
            return
        # 根据订单类型设置不同的到期时间
        if event.order_type == OrderType.QUARTERLY:
            days = 90
        elif event.order_type == OrderType.SEMI_ANNUAL:
            days = 180
        else:
            days = ConfigService.get_int(db, "member_days", 365)

        child.status = MemberStatus.OFFICIAL
        if child.member_expire_time and child.member_expire_time > now:
            child.member_expire_time += timedelta(days=days)
        else:
            child.member_start_time = now
            child.member_expire_time = now + timedelta(days=days)
        child_repo.update(child)
        logger.info(
            f"Child {event.child_id} membership activated: type={event.order_type}, days={days}"
        )
    elif event.order_type == OrderType.OBSERVATION:
        if child.status not in ALLOWED_TO_OBSERVATION:
            logger.warning(
                f"OrderPaidEvent: child {event.child_id} status={child.status} "
                f"not allowed to start OBSERVATION"
            )
            return
        obs_days = ConfigService.get_int(db, "observation_days", 30)
        child.status = MemberStatus.OBSERVATION
        child.member_start_time = now
        child.member_expire_time = now + timedelta(days=obs_days)
        child_repo.update(child)
        logger.info(f"Child {event.child_id} observation period activated: {obs_days} days")
    elif event.order_type == OrderType.PARENT_COURSE:
        obs_days = ConfigService.get_int(db, "observation_days", 30)
        child.status = MemberStatus.OBSERVATION
        child.member_start_time = now
        child.member_expire_time = now + timedelta(days=obs_days)
        child_repo.update(child)
        logger.info(f"Child {event.child_id} parent-course -> observation activated: {obs_days} days")
    else:
        logger.warning(f"OrderPaidEvent: unhandled order_type={event.order_type}")


def handle_deposit_paid_for_child(event, db: Session):
    """押金支付 → 更新孩子押金状态"""
    from backend.common.types import DepositStatus
    from backend.domain.child.models import Child
    from backend.common.base_repo import BaseRepository

    child_repo = BaseRepository(db, Child)
    child = child_repo.get_by_id(event.child_id)
    if child:
        child.deposit_status = DepositStatus.PAID
        child_repo.update(child)
