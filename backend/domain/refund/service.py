# backend/domain/refund/service.py
"""退款域业务逻辑 — 退款申请、审核、退款计算"""

import logging
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

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
from backend.domain.child.service import assert_no_pending_transfer
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

        assert_no_pending_transfer(self.db, order.child_id)

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

        # B3 亲子课开始后不退：课程日当天及以后不可退款
        if order.type == OrderType.PARENT_COURSE and order.parent_course_time_id:
            from backend.domain.parent_course_time.models import ParentCourseTime

            slot = (
                self.db.query(ParentCourseTime)
                .filter(
                    ParentCourseTime.id == order.parent_course_time_id,
                    ParentCourseTime.is_deleted == 0,
                )
                .first()
            )
            if slot and slot.course_date <= date.today().isoformat():
                raise ValidationError("亲子课程已开始，不能退款")

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
        used_days = (date.today() - order.pay_time.date()).days if order.pay_time else 0
        refund_amount = self._calculate(order, used_days)

        # E7/B11：未缴罚款从退款中自动抵扣（不用先缴，退余额）
        from backend.domain.child.models import Child

        child = (
            self.db.query(Child)
            .filter(Child.id == order.child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        outstanding = (
            (child.outstanding_fines or Decimal("0")) if child else Decimal("0")
        )
        fine_deducted = min(refund_amount, outstanding)
        final_amount = refund_amount - fine_deducted

        refund = RefundApplication(
            order_id=data.order_id,
            user_id=user_id,
            child_id=order.child_id,
            refund_amount=final_amount,
            used_days=used_days,  # 使用服务端计算值
            reason=data.reason,
            fine_deducted=fine_deducted,
        )

        # E1：小额退款自动审核通过（默认 ≤500 元，配置 refund_auto_approve_max）
        from backend.common.config_service import ConfigService

        auto_max = ConfigService.get_decimal(
            self.db, "refund_auto_approve_max", Decimal("500")
        )
        if final_amount <= auto_max:
            refund.status = RefundApplication.STATUS_APPROVED
            refund.review_time = datetime.now()
            refund.review_comment = f"系统自动审核（退款≤{auto_max}元，E1决策）"
            order.refund_status = 1  # 退款中
            order.refund_amount = final_amount

        self.refund_repo.create(refund)
        self.db.commit()
        logger.info(
            f"Refund applied: order={data.order_id}, amount={final_amount}, "
            f"fine_deducted={fine_deducted}, status={refund.status}"
        )
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
            # 退款失败：回退 refund 为 PENDING（E1 自动审核可重试）+ 订单状态 + 管理端告警
            try:
                order = db.query(Order).filter(Order.order_no == order_no).first()
                if order:
                    order.refund_status = 3  # FAILED
                    order.pay_status = PayStatus.PAID
                    order.refund_remark = str(e)[:200]

                refund = (
                    db.query(RefundApplication)
                    .filter(RefundApplication.id == refund_id)
                    .first()
                )
                if refund and refund.status == RefundApplication.STATUS_APPROVED:
                    refund.status = RefundApplication.STATUS_PENDING
                    refund.review_comment = (
                        f"退款执行失败已回退待审核，请管理员重试。错误: {str(e)[:150]}"
                    )

                from backend.domain.message.models import SystemMessage

                msg = SystemMessage(
                    user_id=0,
                    title="退款执行失败",
                    content=f"订单 {order_no} 退款执行失败，请手动处理。错误: {str(e)[:200]}",
                    msg_type=1,  # 系统通知
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

        # E7/B11：退款完成时核销已抵扣的未缴罚款
        if refund.fine_deducted and refund.fine_deducted > 0:
            from backend.domain.child.models import Child

            child = (
                self.db.query(Child)
                .filter(Child.id == refund.child_id, Child.is_deleted == 0)
                .with_for_update()
                .first()
            )
            if child:
                child.outstanding_fines = max(
                    Decimal("0"),
                    (child.outstanding_fines or Decimal("0")) - refund.fine_deducted,
                )

        self.db.commit()
        return RefundResponse.model_validate(refund)

    def _calculate(self, order: Order, used_days: int) -> Decimal:
        """退款计算 — 从配置读取天数；前 refund_free_days 天无理由全退（A4）"""
        from backend.common.config_service import ConfigService

        obs_days = ConfigService.get_int(self.db, "observation_days", 45)
        member_days = ConfigService.get_int(self.db, "member_days", 365)
        free_days = ConfigService.get_int(self.db, "refund_free_days", 7)

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

        used = max(0, min(used_days, total_days) - free_days)
        refund = order.amount - (order.amount / total_days * used)
        return max(
            refund.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), Decimal("0")
        )

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
