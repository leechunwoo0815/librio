# backend/domain/order/service.py
"""订单域业务逻辑 — 创建订单、支付处理、退款计算"""

import logging
from decimal import Decimal
from datetime import datetime

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.common.events import OrderPaidEvent, event_bus
from backend.common.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from backend.common.types import MemberStatus, OrderType, PayStatus
from backend.domain.child.models import Child
from backend.domain.order.models import Order
from backend.domain.order.repository import OrderRepository
from backend.domain.order.schemas import (
    OrderCreate,
    OrderResponse,
    OrderPayCallback,
    OrderListResponse,
)

logger = logging.getLogger(__name__)

MULTI_CHILD_DISCOUNT = Decimal("0.9")


class OrderService:
    """订单服务 — 三步漏斗 + 多孩优惠"""

    # 默认价格表（可通过 ConfigService 覆盖）
    _DEFAULT_PRICES = {
        OrderType.PARENT_COURSE: Decimal("99.00"),
        OrderType.OBSERVATION: Decimal("500.00"),
        OrderType.OFFICIAL_MEMBER: Decimal("5400.00"),
        OrderType.QUARTERLY: Decimal("1350.00"),
        OrderType.SEMI_ANNUAL: Decimal("2700.00"),
    }

    _DEFAULT_ORIGINAL_PRICES = {
        OrderType.PARENT_COURSE: 199,
        OrderType.OFFICIAL_MEMBER: 6000,
    }

    def __init__(self, db: Session):
        self.db = db
        self.order_repo = OrderRepository(db)
        self.child_repo = BaseRepository(db, Child)

    def get_price_for_type(self, order_type: OrderType) -> Decimal:
        """公开的价格查询方法"""
        return self._get_price(order_type)

    def get_original_price(self, order_type: OrderType) -> int | None:
        """公开的原价查询方法"""
        from backend.common.config_service import ConfigService

        key_map = {
            OrderType.PARENT_COURSE: "original_price_parent_course",
            OrderType.OFFICIAL_MEMBER: "original_price_official_member",
        }
        key = key_map.get(order_type)
        if key:
            val = ConfigService.get_int(self.db, key, None)
            if val is not None:
                return val
        return self._DEFAULT_ORIGINAL_PRICES.get(order_type)

    def _get_price(self, order_type: OrderType) -> Decimal:
        """从 ConfigService 读取价格，支持动态配置"""
        from backend.common.config_service import ConfigService

        key_map = {
            OrderType.PARENT_COURSE: "price_parent_course",
            OrderType.OBSERVATION: "price_observation",
            OrderType.OFFICIAL_MEMBER: "price_official_member",
            OrderType.QUARTERLY: "price_quarterly",
            OrderType.SEMI_ANNUAL: "price_semi_annual",
        }
        key = key_map.get(order_type)
        if key:
            return ConfigService.get_decimal(
                self.db, key, self._DEFAULT_PRICES[order_type]
            )
        return self._DEFAULT_PRICES.get(order_type, Decimal("0"))

    def create_order(self, user_id: int, order_data: OrderCreate) -> OrderResponse:
        """创建订单 — 校验 + 优惠 + 生成（金额由后端计算）"""
        # 校验孩子
        child = self.child_repo.get_by_id_or_raise(order_data.child_id)
        if child.user_id != user_id:
            raise ForbiddenError("孩子不属于当前用户")

        # 亲子课不可重复（带行锁防止并发重复报名）
        if order_data.type == OrderType.PARENT_COURSE:
            existing_order = (
                self.db.query(Order)
                .filter(
                    Order.child_id == order_data.child_id,
                    Order.type == OrderType.PARENT_COURSE,
                    Order.pay_status.in_([PayStatus.PENDING, PayStatus.PAID]),
                    Order.is_deleted == 0,
                )
                .with_for_update()
                .first()
            )
            if existing_order:
                raise ConflictError("该孩子已报名亲子课程，不可重复报名")

        # 前置状态校验
        from backend.common.types import MemberStatus

        if order_data.type == OrderType.OBSERVATION:
            if child.status not in (MemberStatus.TRIAL,):
                raise ValidationError(
                    f"当前状态({child.status})不允许购买观察期，仅限试读用户"
                )
        elif order_data.type in (
            OrderType.OFFICIAL_MEMBER,
            OrderType.QUARTERLY,
            OrderType.SEMI_ANNUAL,
        ):
            if child.status not in (
                MemberStatus.OBSERVATION,
                MemberStatus.OFFICIAL,
                MemberStatus.EXPIRED,
            ):
                raise ValidationError(
                    f"当前状态({child.status})不允许购买会员"
                )

        # 后端计算金额，不信任前端（从 ConfigService 读取，支持动态配置）
        base_amount = self._get_price(order_data.type)
        if not base_amount:
            raise ValidationError(f"未知订单类型: {order_data.type}")

        # 多孩优惠
        final_amount = self._apply_discount(
            user_id, order_data.type, base_amount, child.status
        )

        order = Order(
            order_no=self.order_repo.generate_order_no(),
            user_id=user_id,
            child_id=order_data.child_id,
            type=order_data.type,
            amount=final_amount,
            remark=order_data.remark,
        )
        created = self.order_repo.create(order)
        self.db.commit()
        logger.info(f"Order created: {created.order_no}, amount={created.amount}")
        return OrderResponse.model_validate(created)

    def _apply_discount(
        self, user_id: int, order_type: int, amount: Decimal, child_status: int = None
    ) -> Decimal:
        """多孩优惠 + 续费折扣（从配置读取，不可叠加，取最低价）"""
        from backend.common.config_service import ConfigService

        if order_type not in (
            OrderType.OBSERVATION,
            OrderType.OFFICIAL_MEMBER,
            OrderType.QUARTERLY,
            OrderType.SEMI_ANNUAL,
        ):
            return amount

        renewal_price = amount
        multi_child_price = amount

        # 续费折扣（EXPIRED 用户续费）
        if child_status == MemberStatus.EXPIRED and order_type in (
            OrderType.OFFICIAL_MEMBER,
            OrderType.QUARTERLY,
            OrderType.SEMI_ANNUAL,
        ):
            renewal_disc = ConfigService.get_decimal(
                self.db, "renewal_discount", Decimal("0.9")
            )
            renewal_price = (amount * renewal_disc).quantize(Decimal("0.01"))

        # P0-6: 多孩优惠 — 检查该用户是否有其他孩子是观察期/正式会员
        from backend.domain.child.models import Child
        active_children = (
            self.db.query(Child)
            .filter(
                Child.user_id == user_id,
                Child.status.in_([MemberStatus.OBSERVATION, MemberStatus.OFFICIAL]),
                Child.is_deleted == 0,
            )
            .count()
        )
        if active_children >= 1:
            discount = ConfigService.get_decimal(
                self.db, "multi_child_discount", MULTI_CHILD_DISCOUNT
            )
            multi_child_price = (amount * discount).quantize(Decimal("0.01"))

        # 不可叠加：取最低价
        return min(renewal_price, multi_child_price)

    def handle_payment_callback(self, callback: OrderPayCallback) -> OrderResponse:
        """处理支付回调 — 校验金额 + 更新状态 + 发布事件"""
        order = (
            self.db.query(Order)
            .filter(
                Order.order_no == callback.order_no,
                Order.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if not order:
            raise NotFoundError("订单不存在")

        if order.pay_status == PayStatus.PAID:
            logger.warning(f"Order {callback.order_no} already paid")
            return OrderResponse.model_validate(order)

        if callback.amount != order.amount:
            raise PaymentError(
                f"支付金额不一致: 回调{callback.amount}, 订单{order.amount}"
            )

        order.pay_status = PayStatus.PAID
        order.pay_type = callback.pay_type
        order.trade_no = callback.trade_no
        order.pay_time = datetime.now()
        self.order_repo.update(order)

        # 发布支付成功事件
        event_bus.publish(
            OrderPaidEvent(
                order_id=order.id,
                child_id=order.child_id,
                order_type=order.type,
                amount=Decimal(str(order.amount)),
            ),
            db=self.db,
        )

        self.db.commit()
        logger.info(f"Payment received: {callback.order_no}")
        return OrderResponse.model_validate(order)

    # ==================== 升级差额计算 ====================

    # 升级路径：季度 → 半年 → 年费
    _UPGRADE_HIERARCHY = {
        OrderType.QUARTERLY: (90, OrderType.SEMI_ANNUAL),
        OrderType.SEMI_ANNUAL: (180, OrderType.OFFICIAL_MEMBER),
        OrderType.OFFICIAL_MEMBER: (365, None),  # 最高级，不可再升
    }

    def get_upgrade_options(self, child_id: int) -> list[dict]:
        """查询可升级选项及差价"""
        from backend.common.types import MemberStatus

        child = self.child_repo.get_by_id_or_raise(child_id)
        if child.status != MemberStatus.OFFICIAL:
            return []
        if not child.member_expire_time or not child.member_start_time:
            return []

        # 查找当前生效的最短周期订单
        current_order = (
            self.db.query(Order)
            .filter(
                Order.child_id == child_id,
                Order.type.in_([
                    OrderType.QUARTERLY,
                    OrderType.SEMI_ANNUAL,
                    OrderType.OFFICIAL_MEMBER,
                ]),
                Order.pay_status == PayStatus.PAID,
                Order.is_deleted == 0,
            )
            .order_by(Order.pay_time.desc())
            .first()
        )
        if not current_order:
            return []

        current_type = current_order.type
        hierarchy = self._UPGRADE_HIERARCHY.get(current_type)
        if not hierarchy or hierarchy[1] is None:
            return []  # 已是最高级

        current_total_days, next_type = hierarchy
        remaining_days = max(
            0, (child.member_expire_time - datetime.now()).days
        )

        options = []
        # 计算当前剩余价值
        current_price = self._get_price(current_type)
        remaining_value = (
            current_price * Decimal(str(remaining_days)) / Decimal(str(current_total_days))
        ).quantize(Decimal("0.01"))

        # 可升级到的目标类型
        target_types = []
        if next_type == OrderType.SEMI_ANNUAL:
            target_types = [OrderType.SEMI_ANNUAL, OrderType.OFFICIAL_MEMBER]
        elif next_type == OrderType.OFFICIAL_MEMBER:
            target_types = [OrderType.OFFICIAL_MEMBER]

        for target_type in target_types:
            target_price = self._get_price(target_type)
            upgrade_price = max(target_price - remaining_value, Decimal("0"))
            target_days = self._UPGRADE_HIERARCHY.get(target_type, (365, None))[0]
            options.append({
                "current_type": current_type,
                "target_type": target_type,
                "target_price": str(target_price),
                "target_days": target_days,
                "remaining_value": str(remaining_value),
                "upgrade_price": str(upgrade_price.quantize(Decimal("0.01"))),
            })

        return options

    def create_upgrade_order(
        self, user_id: int, child_id: int, target_type: int
    ) -> OrderResponse:
        """创建升级订单 — 补齐差额"""
        from backend.common.types import MemberStatus

        child = self.child_repo.get_by_id_or_raise(child_id)
        if child.user_id != user_id:
            raise ForbiddenError("孩子不属于当前用户")
        if child.status != MemberStatus.OFFICIAL:
            raise ValidationError("仅正式会员可升级")

        # 计算升级差价
        options = self.get_upgrade_options(child_id)
        option = next((o for o in options if o["target_type"] == target_type), None)
        if not option:
            raise ValidationError("当前会员类型不支持升级到目标类型")

        upgrade_amount = Decimal(option["upgrade_price"])
        if upgrade_amount <= 0:
            raise ValidationError("无需升级，当前剩余价值已超过目标价格")

        order = Order(
            order_no=self.order_repo.generate_order_no(),
            user_id=user_id,
            child_id=child_id,
            type=target_type,
            amount=upgrade_amount,
            remark=f"升级差额（{OrderType(option['current_type']).name} → {OrderType(target_type).name}）",
        )
        created = self.order_repo.create(order)
        self.db.commit()
        logger.info(
            f"Upgrade order created: {created.order_no}, amount={created.amount}"
        )
        return OrderResponse.model_validate(created)

    def get_order(self, order_id: int) -> OrderResponse:
        return OrderResponse.model_validate(
            self.order_repo.get_by_id_or_raise(order_id)
        )

    def get_user_orders(
        self, user_id: int, page: int = 1, page_size: int = 10
    ) -> OrderListResponse:
        orders, total = self.order_repo.get_by_user_id(user_id, page, page_size)
        return OrderListResponse.create(
            items=[OrderResponse.model_validate(o) for o in orders],
            total=total,
            page=page,
            page_size=page_size,
        )

    def calculate_refund(self, order_id: int, used_days: int) -> dict:
        """计算退款金额 — 按实付金额 × 剩余天数比例"""
        order = self.order_repo.get_by_id_or_raise(order_id)
        if order.pay_status != PayStatus.PAID:
            raise ValidationError("订单未支付，无法退款")

        # 从配置读取天数
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
            return {"refund_amount": order.amount, "daily_rate": Decimal("0"), "used_amount": Decimal("0"), "total_days": 0}

        used = min(used_days, total_days)
        daily_rate = (order.amount / total_days).quantize(Decimal("0.01"))
        used_amount = (daily_rate * used).quantize(Decimal("0.01"))
        refund = max((order.amount - used_amount).quantize(Decimal("0.01")), Decimal("0"))
        return {
            "refund_amount": refund,
            "daily_rate": daily_rate,
            "used_amount": used_amount,
            "total_days": total_days,
        }

    def cancel_order(self, order_id: int, user_id: int) -> OrderResponse:
        """取消未支付的订单"""
        order = self.order_repo.get_by_id_or_raise(order_id)
        if order.user_id != user_id:
            raise ValidationError("订单不存在")
        if order.pay_status != 0:
            raise ValidationError("仅可取消未支付的订单")
        order.pay_status = PayStatus.CLOSED
        self.db.commit()
        self.db.refresh(order)
        return OrderResponse.model_validate(order)
