# backend/events/order_handlers.py
"""订单/押金相关事件处理器"""

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _mark_activation_issue(db: Session, event, reason: str) -> None:
    """F7：支付成功但会员未激活 → 订单留痕 + OperationLog（对账任务/人工队列用）

    路线：保留支付、不抛异常回滚——钱已到账的交易不交给回调重试机制决定资金状态。
    """
    from backend.domain.admin.models import OperationLog
    from backend.domain.order.models import Order

    order = (
        db.query(Order)
        .filter(Order.id == event.order_id, Order.is_deleted == 0)
        .first()
    )
    if order:
        order.activation_issue = 1
    db.add(
        OperationLog(
            admin_id=0,
            module="order",
            operation="paid_not_activated",
            content=(
                f"order={event.order_id}, child={event.child_id}, "
                f"type={event.order_type}, 已支付但未激活（{reason}），请人工处理"
            ),
        )
    )
    db.flush()


def handle_order_paid_for_child(event, db: Session):
    """订单支付 → 更新孩子会员状态（含状态迁移合法性校验）"""
    from datetime import datetime, timedelta
    from backend.common.types import OrderType, MemberStatus, PayStatus
    from backend.domain.child.models import Child
    from backend.common.base_repo import BaseRepository
    from backend.common.config_service import ConfigService

    child = (
        db.query(Child)
        .filter(Child.id == event.child_id, Child.is_deleted == 0)
        .with_for_update()
        .first()
    )
    child_repo = BaseRepository(db, Child)
    if not child:
        logger.warning(f"OrderPaidEvent: child_id={event.child_id} not found")
        _mark_activation_issue(db, event, "child_not_found")
        return

    if child.status == MemberStatus.EXITED:
        logger.warning(
            f"OrderPaidEvent: child {event.child_id} is EXITED, cannot restore"
        )
        _mark_activation_issue(db, event, "child_exited")
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
            _mark_activation_issue(
                db, event, f"status_not_allowed_for_official({child.status})"
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
        # F16：升级/抵扣单（upgrade_deduct>0）差额已按剩余价值抵扣（A6），
        # 会员期重置起算，禁止"抵扣+叠加"双重受益；普通购买/续费仍叠加。
        is_upgrade = False
        if event.order_id:
            from backend.domain.order.models import Order

            paid_order = db.query(Order).filter(Order.id == event.order_id).first()
            is_upgrade = paid_order is not None and (paid_order.upgrade_deduct or 0) > 0
        if is_upgrade:
            child.member_start_time = now
            child.member_expire_time = now + timedelta(days=days)
        elif child.member_expire_time and child.member_expire_time > now:
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
            _mark_activation_issue(
                db, event, f"status_not_allowed_for_observation({child.status})"
            )
            return
        obs_days = ConfigService.get_int(db, "observation_days", 45)
        child.status = MemberStatus.OBSERVATION
        child.member_start_time = now
        child.member_expire_time = now + timedelta(days=obs_days)
        # A1 双轨制：标记报名来源（有已支付亲子课订单=亲子课转化，否则=直接观察期）
        if not child.enroll_source:
            from backend.domain.order.models import Order

            has_parent_course = (
                db.query(Order)
                .filter(
                    Order.child_id == event.child_id,
                    Order.type == OrderType.PARENT_COURSE,
                    Order.pay_status == PayStatus.PAID,
                    Order.is_deleted == 0,
                )
                .first()
            )
            child.enroll_source = 1 if has_parent_course else 2
        child_repo.update(child)
        logger.info(
            f"Child {event.child_id} observation period activated: {obs_days} days, "
            f"source={child.enroll_source}"
        )
    elif event.order_type == OrderType.PARENT_COURSE:
        # A1 双轨制：亲子课支付不再直接开通观察期（观察期为 500 元独立产品），
        # 仅标记转化来源，孩子保持 TRIAL 直至购买观察期
        if not child.enroll_source:
            child.enroll_source = 1
            child_repo.update(child)
        logger.info(f"Child {event.child_id} parent-course paid, source=1")
    else:
        logger.warning(f"OrderPaidEvent: unhandled order_type={event.order_type}")
        _mark_activation_issue(db, event, f"unhandled_order_type({event.order_type})")


def handle_deposit_paid_for_child(event, db: Session):
    """押金支付 → 更新孩子押金状态"""
    from backend.common.types import DepositStatus
    from backend.domain.child.models import Child
    from backend.common.base_repo import BaseRepository

    child_repo = BaseRepository(db, Child)
    child = (
        db.query(Child)
        .filter(Child.id == event.child_id, Child.is_deleted == 0)
        .with_for_update()
        .first()
    )
    if child:
        child.deposit_status = DepositStatus.PAID
        child_repo.update(child)
