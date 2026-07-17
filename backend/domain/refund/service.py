# backend/domain/refund/service.py
"""退款域业务逻辑 — 退款申请、审核、退款计算"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from backend.common.types import OrderType, PayStatus
from backend.domain.order.models import Order
from backend.domain.refund.models import RefundApplication
from backend.domain.refund.repository import RefundRepository
from backend.domain.refund.schemas import RefundCreate, RefundAudit, RefundResponse

logger = logging.getLogger(__name__)


class RefundService:
    """退款服务"""

    def __init__(self, db: Session):
        self.db = db
        self.refund_repo = RefundRepository(db)
        self.order_repo = BaseRepository(db, Order)

    def apply_refund(self, user_id: int, data: RefundCreate) -> RefundResponse:
        """提交退款申请"""
        order = (
            self.db.query(Order)
            .filter(Order.id == data.order_id, Order.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not order:
            from backend.common.exceptions import NotFoundError

            raise NotFoundError(f"Order(id={data.order_id}) 不存在")
        if order.user_id != user_id:
            raise ForbiddenError("订单不属于当前用户")
        if order.pay_status != PayStatus.PAID:
            raise ValidationError("订单未支付，无法退款")

        existing = (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.order_id == data.order_id,
                RefundApplication.status == RefundApplication.STATUS_PENDING,
                RefundApplication.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if existing:
            raise ConflictError("该订单已有正在处理的退款申请")

        # P0-5: 亲子课退款规则 — 课程开始后不可退款
        from backend.common.types import OrderType

        if order.type == OrderType.PARENT_COURSE:
            from backend.domain.parent_course_time.models import ParentCourseTime
            from datetime import datetime as dt

            now = dt.now()
            # 查找该用户已报名且已开始的亲子课
            course_started = (
                self.db.query(ParentCourseTime)
                .filter(
                    ParentCourseTime.is_deleted == 0,
                    ParentCourseTime.course_date <= now.strftime("%Y-%m-%d"),
                )
                .first()
            )
            if course_started:
                # 如果课程日期已到，且当前时间已过开始时间
                course_start = dt.strptime(
                    f"{course_started.course_date} {course_started.start_time}",
                    "%Y-%m-%d %H:%M",
                )
                if now >= course_start:
                    raise ValidationError("亲子课已开始，无法退款")

        # P2-7: 365天内同一孩子仅可退款1次（防滥用循环退款）
        from sqlalchemy import func

        one_year_ago = datetime.now().replace(year=datetime.now().year - 1)
        approved_count = (
            self.db.query(func.count(RefundApplication.id))
            .filter(
                RefundApplication.child_id == order.child_id,
                RefundApplication.status == RefundApplication.STATUS_APPROVED,
                RefundApplication.create_time >= one_year_ago,
                RefundApplication.is_deleted == 0,
            )
            .scalar()
        )
        if approved_count and approved_count > 0:
            raise ValidationError("同一孩子 365 天内仅可退款 1 次，已超出年度上限")

        # P0 全局退出拦截网：校验是否有未归还的实体书
        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus as BS

        active_borrows = (
            self.db.query(BorrowRecord.id)
            .filter(
                BorrowRecord.child_id == order.child_id,
                BorrowRecord.status.in_([BS.BORROWING, BS.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .with_for_update()
            .count()
        )
        if active_borrows > 0:
            raise ValidationError(
                "您名下尚有未归还的实体图书，请先至门店归还后再申请退款"
            )

        # 计算退款金额（服务端计算已用天数，不信任前端）
        used_days = (datetime.now() - order.pay_time).days if order.pay_time else 0
        refund_amount = self._calculate(order, used_days)

        refund = RefundApplication(
            order_id=data.order_id,
            user_id=user_id,
            child_id=order.child_id,
            refund_amount=refund_amount,
            used_days=used_days,  # 使用服务端计算值
            reason=data.reason,
        )
        self.refund_repo.create(refund)
        self.db.commit()
        logger.info(f"Refund applied: order={data.order_id}, refund={refund_amount}")
        return RefundResponse.model_validate(refund)

    def audit_refund(self, refund_id: int, audit: RefundAudit) -> RefundResponse:
        """审核退款 — 带行锁防止双重审批"""
        refund = (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.id == refund_id, RefundApplication.is_deleted == 0
            )
            .with_for_update()
            .first()
        )
        if not refund:
            raise NotFoundError("退款申请不存在")
        if refund.status != RefundApplication.STATUS_PENDING:
            raise ConflictError("申请已处理")

        refund.status = audit.status
        refund.reviewer_id = audit.admin_id
        refund.review_time = datetime.now()
        if audit.remark:
            refund.review_comment = audit.remark

        # 审核通过 → 标记订单退款状态（pay_status 保持 PAID，退款由 refund_status 跟踪）
        if audit.status == RefundApplication.STATUS_APPROVED:
            order = (
                self.db.query(Order)
                .filter(Order.id == refund.order_id, Order.is_deleted == 0)
                .with_for_update()
                .first()
            )
            if order:
                order.refund_status = 1  # 退款中
                order.refund_amount = refund.refund_amount

        self.db.commit()
        return RefundResponse.model_validate(refund)

    @staticmethod
    async def _execute_wechat_refund(
        refund_id: int, order_no: str, amount: Decimal, reason: str
    ):
        """调用退款 API（独立 session，供 BackgroundTasks 调用）"""
        import uuid
        from backend.database import get_session

        db = get_session()()
        try:
            from backend.config import get_settings
            from backend.common.dependencies import get_payment_gateway
            from backend.common.gateways.payment.types import PaymentRefundRequest

            settings = get_settings()
            if settings.DEBUG:
                logger.info(f"DEBUG mode: skipping WeChat refund for order={order_no}")
                db.close()
                return

            # 重新查询确保活跃 session
            order = db.query(Order).filter(Order.order_no == order_no).first()
            if not order:
                logger.error(f"Refund task: order not found: {order_no}")
                db.close()
                return

            gateway = get_payment_gateway()
            out_refund_no = f"RF{uuid.uuid4().hex[:16]}"

            result = await gateway.refund(
                PaymentRefundRequest(
                    out_trade_no=order_no,
                    out_refund_no=out_refund_no,
                    total_amount=amount,
                    refund_amount=amount,
                    reason=reason or "管理员审核通过",
                )
            )
            logger.info(f"WeChat refund submitted: order={order_no}, result={result}")
            # 微信退款是异步的，状态由回调或定时任务更新
        except Exception as e:
            logger.error(f"WeChat refund failed: order={order_no}, error={e}")
            # 退款失败：更新订单状态 + 写入消息
            try:
                order = db.query(Order).filter(Order.order_no == order_no).first()
                if order:
                    order.refund_status = 3  # FAILED
                    order.pay_status = PayStatus.PAID
                    order.refund_remark = str(e)[:200]

                from backend.domain.message.models import SystemMessage

                msg = SystemMessage(
                    user_id=0,
                    title="退款执行失败",
                    content=f"订单 {order_no} 退款执行失败，请手动处理。错误: {str(e)[:200]}",
                    msg_type=7,
                    priority=2,
                )
                db.add(msg)
                db.commit()
            except SQLAlchemyError as e2:
                logger.error(
                    f"Failed to save refund failure state for order {order_no}: {e2}"
                )
        finally:
            db.close()

    def mark_refunded(self, order_no: str) -> RefundResponse:
        """微信退款回调 — 标记退款完成"""
        order = (
            self.db.query(Order)
            .filter(Order.order_no == order_no, Order.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not order:
            raise NotFoundError(f"订单不存在: {order_no}")

        refund = (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.order_id == order.id,
                RefundApplication.status == RefundApplication.STATUS_APPROVED,
            )
            .with_for_update()
            .first()
        )
        if not refund:
            raise ConflictError("无待完成的退款申请")

        refund.status = RefundApplication.STATUS_COMPLETED
        refund.actual_refund_amount = refund.refund_amount
        refund.refund_time = datetime.now()
        order.refund_status = 2  # REFUND_DONE
        order.pay_status = PayStatus.REFUNDED
        self.db.commit()
        return RefundResponse.model_validate(refund)

    def _calculate(self, order: Order, used_days: int) -> Decimal:
        """退款计算 — 从配置读取天数"""
        from backend.common.config_service import ConfigService

        obs_days = ConfigService.get_int(self.db, "observation_days", 30)
        member_days = ConfigService.get_int(self.db, "member_days", 365)

        if order.type == OrderType.OBSERVATION:
            total_days = obs_days
        elif order.type == OrderType.OFFICIAL_MEMBER:
            total_days = member_days
        elif order.type == OrderType.QUARTERLY:
            total_days = 90
        elif order.type == OrderType.SEMI_ANNUAL:
            total_days = 180
        else:
            return order.amount

        used = min(used_days, total_days)
        refund = order.amount - (order.amount / total_days * used)
        return max(refund.quantize(Decimal("0.01")), Decimal("0"))

    def get_refund_with_order(self, refund_id: int) -> tuple | None:
        refund = (
            self.db.query(RefundApplication)
            .filter(RefundApplication.id == refund_id)
            .first()
        )
        if not refund:
            return None
        order = self.db.query(Order).filter(Order.id == refund.order_id).first()
        return (refund, order)

    def get_refund(self, refund_id: int) -> RefundResponse:
        return RefundResponse.model_validate(
            self.refund_repo.get_by_id_or_raise(refund_id)
        )

    def get_user_refunds(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> dict:
        records, total = self.refund_repo.get_by_user(user_id, page, page_size)
        return {
            "items": [RefundResponse.model_validate(r) for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
