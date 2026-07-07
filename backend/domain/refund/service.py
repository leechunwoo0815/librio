# backend/domain/refund/service.py
"""退款域业务逻辑 — 退款申请、审核、退款计算"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.exceptions import ConflictError, ForbiddenError, ValidationError
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
        order = self.order_repo.get_by_id_or_raise(data.order_id)
        if order.user_id != user_id:
            raise ForbiddenError("订单不属于当前用户")
        if order.pay_status != PayStatus.PAID:
            raise ValidationError("订单未支付，无法退款")

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

        # P0 全局退出拦截网：校验是否有未归还的实体书
        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus as BS

        active_borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == order.child_id,
                BorrowRecord.status.in_([BS.BORROWING, BS.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )
        if active_borrows > 0:
            raise ValidationError("您名下尚有未归还的实体图书，请先至门店归还后再申请退款")

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
        """审核退款"""
        refund = self.refund_repo.get_by_id_or_raise(refund_id)
        if refund.status != RefundApplication.STATUS_PENDING:
            raise ConflictError("申请已处理")

        refund.status = audit.status
        refund.reviewer_id = audit.admin_id
        refund.review_time = datetime.now()
        if audit.remark:
            refund.review_comment = audit.remark

        # 审核通过 → 更新订单退款状态
        if audit.status == RefundApplication.STATUS_APPROVED:
            order = self.order_repo.get_by_id(refund.order_id)
            if order:
                order.refund_status = 1  # 退款中
                order.refund_amount = refund.refund_amount
                self.order_repo.update(order)

        self.refund_repo.update(refund)
        self.db.commit()
        return RefundResponse.model_validate(refund)

    async def _execute_wechat_refund_async(self, refund, order):
        """调用微信退款 API（异步版本，供 BackgroundTasks 调用）"""
        import uuid

        try:
            from backend.integrations.wechat.pay_v3 import WeChatPayV3
            from backend.config import get_settings

            settings = get_settings()
            if settings.DEBUG:
                logger.info(f"DEBUG mode: skipping WeChat refund for order={order.order_no}")
                return

            pay = WeChatPayV3()
            total_cent = int(order.amount * 100)
            refund_cent = int(refund.refund_amount * 100)
            out_refund_no = f"RF{uuid.uuid4().hex[:16]}"

            result = await pay.refund(
                out_trade_no=order.order_no,
                out_refund_no=out_refund_no,
                total_cent=total_cent,
                refund_cent=refund_cent,
                reason=refund.review_comment or "管理员审核通过",
            )
            logger.info(f"WeChat refund submitted: order={order.order_no}, result={result}")
            # 微信退款是异步的，状态由回调或定时任务更新
        except Exception as e:
            logger.error(f"WeChat refund failed: order={order.order_no}, error={e}")
            # 退款失败：更新订单状态 + 写入消息
            try:
                order.refund_status = 3  # FAILED
                order.refund_remark = str(e)[:200]
                self.order_repo.update(order)
                self.db.commit()

                from backend.domain.message.models import SystemMessage
                msg = SystemMessage(
                    user_id=0,
                    title="退款执行失败",
                    content=f"订单 {order.order_no} 退款执行失败，请手动处理。错误: {str(e)[:200]}",
                    msg_type=7,
                    priority=2,
                )
                self.db.add(msg)
                self.db.commit()
            except Exception:
                pass

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

    def get_refund(self, refund_id: int) -> RefundResponse:
        return RefundResponse.model_validate(
            self.refund_repo.get_by_id_or_raise(refund_id)
        )

    def get_user_refunds(self, user_id: int) -> list[RefundResponse]:
        return [
            RefundResponse.model_validate(r)
            for r in self.refund_repo.get_by_user(user_id)
        ]
