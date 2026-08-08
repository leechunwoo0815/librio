# backend/domain/order/service.py
"""订单域业务逻辑 — 创建订单、支付处理、退款计算"""

import logging
from decimal import Decimal, ROUND_HALF_UP
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
from backend.domain.child.service import assert_no_pending_transfer
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

    # 会员类订单类型（多孩资格/快照判定用，亲子课不计）
    MEMBER_TYPES = (
        OrderType.OBSERVATION,
        OrderType.OFFICIAL_MEMBER,
        OrderType.QUARTERLY,
        OrderType.SEMI_ANNUAL,
    )

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

    def get_observation_days(self) -> int:
        """观察期天数（A3，从配置读取，供 tiers 文案动态生成，禁硬编码）"""
        from backend.common.config_service import ConfigService

        return ConfigService.get_int(self.db, "observation_days", 45)

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

        # 权益转让校验：非亲子课订单检查转让锁定
        if order_data.type != OrderType.PARENT_COURSE:
            assert_no_pending_transfer(self.db, order_data.child_id)
            # F22：同孩子同类型 PENDING 订单拦截（此前可重复下单，超时关闭前堆叠）
            existing_pending = (
                self.db.query(Order)
                .filter(
                    Order.child_id == order_data.child_id,
                    Order.type == order_data.type,
                    Order.pay_status == PayStatus.PENDING,
                    Order.is_deleted == 0,
                )
                .with_for_update()
                .first()
            )
            if existing_pending:
                raise ConflictError("该孩子已有同类型的待支付订单，请先完成支付或取消")

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

            # B3 时段关联：名额校验（已支付订单计数口径，无需占/释放名额字段）
            if order_data.slot_id:
                from backend.domain.parent_course_time.models import (
                    ParentCourseTime,
                )

                slot = (
                    self.db.query(ParentCourseTime)
                    .filter(
                        ParentCourseTime.id == order_data.slot_id,
                        ParentCourseTime.is_deleted == 0,
                    )
                    .first()
                )
                if not slot:
                    raise ValidationError("所选上课时间段不存在")
                if slot.status != 1:
                    raise ValidationError("该时间段名额已满，请选择其他时间")
                paid_count = (
                    self.db.query(Order)
                    .filter(
                        Order.parent_course_time_id == slot.id,
                        Order.type == OrderType.PARENT_COURSE,
                        Order.pay_status == PayStatus.PAID,
                        Order.is_deleted == 0,
                    )
                    .count()
                )
                if paid_count >= slot.max_participants:
                    raise ConflictError("该时间段名额已满，请选择其他时间")

        # 前置状态校验
        from backend.common.types import MemberStatus

        if order_data.type == OrderType.OBSERVATION:
            if child.status not in (MemberStatus.TRIAL,):
                raise ValidationError(
                    f"当前状态({child.status})不允许购买观察期，仅限试读用户"
                )
            # B3 漏斗校验：需先完成亲子课程（存在已支付亲子课订单）
            has_parent_course = (
                self.db.query(Order)
                .filter(
                    Order.child_id == order_data.child_id,
                    Order.type == OrderType.PARENT_COURSE,
                    Order.pay_status == PayStatus.PAID,
                    Order.is_deleted == 0,
                )
                .first()
            )
            if not has_parent_course:
                # A1 双轨制：亲子课为推荐入口，非强制前置；配置可恢复强制（保留修改接口）
                from backend.common.config_service import ConfigService

                required = ConfigService.get_bool(
                    self.db, "parent_course_required", False
                )
                if required:
                    raise ValidationError("请先完成亲子课程并获得测评报告")
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
                raise ValidationError(f"当前状态({child.status})不允许购买会员")

        # 后端计算金额，不信任前端（从 ConfigService 读取，支持动态配置）
        base_amount = self._get_price(order_data.type)
        if not base_amount:
            raise ValidationError(f"未知订单类型: {order_data.type}")

        # 多孩优惠
        final_amount = self._apply_discount(
            user_id,
            order_data.type,
            base_amount,
            child.status,
            order_data.child_id,
            child.member_expire_time,
        )

        # A6：观察期中途升级 — 按剩余天数抵扣观察期剩余价值（upgrade_deduct_enabled）
        upgrade_deduct = Decimal("0")
        if (
            order_data.type
            in (
                OrderType.OFFICIAL_MEMBER,
                OrderType.QUARTERLY,
                OrderType.SEMI_ANNUAL,
            )
            and child.status == MemberStatus.OBSERVATION
        ):
            upgrade_deduct = self._calc_observation_credit(child)
            final_amount = max(Decimal("0"), final_amount - upgrade_deduct)

        order = Order(
            order_no=self.order_repo.generate_order_no(),
            user_id=user_id,
            child_id=order_data.child_id,
            type=order_data.type,
            amount=final_amount,
            remark=order_data.remark,
            parent_course_time_id=order_data.slot_id,
            upgrade_deduct=upgrade_deduct,
        )
        created = self.order_repo.create(order)
        self.db.commit()
        logger.info(f"Order created: {created.order_no}, amount={created.amount}")
        return OrderResponse.model_validate(created)

    def _mark_paid_member_ever(self, order) -> None:
        """F5 快照：会员类订单支付成功 → user.paid_member_ever=1

        财务 purge 删除历史订单后，多孩资格仍以该快照为准（决策：资格不随数据删除失效）。
        """
        if order.type not in self.MEMBER_TYPES:
            return
        from backend.domain.user.models import User

        # F-003：快照写 user.paid_member_ever 必须行锁（并发双订单同事务防双写）
        user = (
            self.db.query(User)
            .filter(User.id == order.user_id)
            .with_for_update()
            .first()
        )
        if user and not user.paid_member_ever:
            user.paid_member_ever = 1

    def _apply_discount(
        self,
        user_id: int,
        order_type: int,
        amount: Decimal,
        child_status: int = None,
        child_id: int = None,
        member_expire_time: datetime = None,
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

        # 续费折扣（F8：缓冲期内——到期时刻起算（含 day 0）至 member_grace_days 天）
        # 自然日口径（与 fine_policy 一致）：到期日当天=0，次日=1，缓冲期内=0..grace_days
        now = datetime.now()
        days_expired = (
            (now.date() - member_expire_time.date()).days
            if member_expire_time is not None
            else None
        )
        grace_days = ConfigService.get_int(self.db, "member_grace_days", 15)
        if (
            member_expire_time is not None
            and member_expire_time
            <= now  # 到期时刻已过（防止"今晚才到期"未过期误入窗口）
            and days_expired is not None
            and 0 <= days_expired <= grace_days
            and order_type
            in (
                OrderType.OFFICIAL_MEMBER,
                OrderType.QUARTERLY,
                OrderType.SEMI_ANNUAL,
            )
        ):
            renewal_disc = ConfigService.get_decimal(
                self.db, "renewal_discount", Decimal("0.9")
            )
            renewal_price = (amount * renewal_disc).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # P0-6: 多孩优惠 — 检查该用户是否有其他孩子是观察期/正式会员
        # 排除报名孩子自身，避免单孩子也享受多孩优惠
        # F5：历史付过费的孩子（含 EXITED 复活场景）同样计入多孩资格
        from backend.domain.child.models import Child

        member_order_children = (
            self.db.query(Order.child_id)
            .filter(
                Order.user_id == user_id,
                Order.type.in_(
                    [
                        OrderType.OBSERVATION,
                        OrderType.OFFICIAL_MEMBER,
                        OrderType.QUARTERLY,
                        OrderType.SEMI_ANNUAL,
                    ]
                ),
                Order.pay_status == PayStatus.PAID,
                Order.is_deleted == 0,
            )
            .distinct()
            .subquery()
        )
        active_children = self.db.query(Child).filter(
            Child.user_id == user_id,
            (
                Child.status.in_([MemberStatus.OBSERVATION, MemberStatus.OFFICIAL])
                | Child.id.in_(member_order_children)
            ),
            Child.is_deleted == 0,
        )
        if child_id is not None:
            active_children = active_children.filter(Child.id != child_id)
        active_children_count = active_children.count()
        # F5 快照兜底：历史订单被财务 purge 后，仍以 user.paid_member_ever 判定资格
        if active_children_count < 1:
            from backend.domain.user.models import User

            paid_ever = (
                self.db.query(User.paid_member_ever)
                .filter(User.id == user_id, User.is_deleted == 0)
                .scalar()
            )
            if paid_ever:
                active_children_count = 1
        if active_children_count >= 1:
            discount = ConfigService.get_decimal(
                self.db, "multi_child_discount", MULTI_CHILD_DISCOUNT
            )
            multi_child_price = (amount * discount).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # 不可叠加：取最低价
        return min(renewal_price, multi_child_price)

    def _calc_observation_credit(self, child) -> Decimal:
        """A6：观察期剩余价值 = 实付 ÷ observation_days × 剩余天数"""
        from decimal import ROUND_HALF_UP

        from backend.common.config_service import ConfigService

        if not ConfigService.get_bool(self.db, "upgrade_deduct_enabled", True):
            return Decimal("0")
        if not child.member_expire_time:
            return Decimal("0")
        remaining = (child.member_expire_time - datetime.now()).days
        if remaining <= 0:
            return Decimal("0")

        obs_order = (
            self.db.query(Order)
            .filter(
                Order.child_id == child.id,
                Order.type == OrderType.OBSERVATION,
                Order.pay_status == PayStatus.PAID,
                Order.is_deleted == 0,
            )
            .order_by(Order.pay_time.desc())
            .first()
        )
        if not obs_order:
            return Decimal("0")

        obs_days = ConfigService.get_int(self.db, "observation_days", 45)
        credit = Decimal(str(obs_order.amount)) / obs_days * remaining
        return min(
            credit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            Decimal(str(obs_order.amount)),
        )

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

        # F-007：已退款/退款中的订单忽略支付回调（防资金状态被反转覆盖）
        if order.pay_status in (PayStatus.REFUNDED, PayStatus.REFUNDING):
            logger.warning(
                f"Order {callback.order_no} in refund state, payment callback ignored"
            )
            return OrderResponse.model_validate(order)

        # F26：trade_no 重复 = 同一笔支付被两次入账（DB 唯一索引兜底 + 服务层前置检查）
        dup_trade = (
            self.db.query(Order.id)
            .filter(
                Order.trade_no == callback.trade_no,
                Order.id != order.id,
                Order.is_deleted == 0,
            )
            .first()
        )
        if dup_trade:
            raise PaymentError(f"交易流水号 {callback.trade_no} 已关联其他订单")

        # F75-③：回调 trade_state 消费——非 SUCCESS 不标记已支付（纵深防御）
        if callback.trade_state and callback.trade_state != "SUCCESS":
            logger.warning(
                f"Order callback non-SUCCESS: {callback.order_no}, trade_state={callback.trade_state}"
            )
            return OrderResponse.model_validate(order)

        if callback.amount != order.amount:
            raise PaymentError(
                f"支付金额不一致: 回调{callback.amount}, 订单{order.amount}"
            )

        # 记录迟到支付（CLOSED → PAID）
        was_closed = order.pay_status == PayStatus.CLOSED

        order.pay_status = PayStatus.PAID
        order.pay_type = callback.pay_type
        order.trade_no = callback.trade_no
        order.pay_time = datetime.now()
        self.order_repo.update(order)
        self._mark_paid_member_ever(order)  # F5 快照（purge 财务数据后多孩资格仍有效）

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

        # 迟到支付补记操作日志（不入事务，不影响主流程）
        if was_closed:
            try:
                from backend.domain.admin.services.system_service import (
                    AdminSystemService,
                )

                system_service = AdminSystemService(self.db)
                system_service.write_operation_log(
                    admin_id=None,
                    module="order",
                    operation="late_payment",
                    content=f"订单 {callback.order_no} 迟到支付激活（原 CLOSED），金额={callback.amount}",
                )
            except Exception:
                logger.exception(f"迟到支付日志写入失败: {callback.order_no}")

        logger.info(f"Payment received: {callback.order_no}")
        return OrderResponse.model_validate(order)

    # ==================== A5 iOS 替代支付路径 ====================

    async def generate_pay_code(self, order_no: str, gateway) -> dict:
        """A5 门店收款码：为待支付订单生成微信支付参数/收款码（管理端展示，家长 iPhone 扫码付）"""
        order = (
            self.db.query(Order)
            .filter(Order.order_no == order_no, Order.is_deleted == 0)
            .first()
        )
        if not order:
            raise NotFoundError("订单不存在")
        if order.pay_status not in (PayStatus.PENDING, PayStatus.CLOSED):
            raise ConflictError("订单状态不允许支付")

        from backend.common.gateways.payment.types import (
            PaymentOrderRequest,
            yuan_to_cents,
        )

        result = await gateway.create_order(
            PaymentOrderRequest(
                out_trade_no=order.order_no,
                amount=Decimal(yuan_to_cents(order.amount)),  # 元入分出（F1 修复）
                description=f"DmkWords订单 {order.order_no}",
            )
        )
        return {
            "order_no": order.order_no,
            "amount": str(order.amount),
            "pay_params": getattr(result, "pay_params", {}) or {},
        }

    def confirm_bank_transfer(
        self, order_no: str, trade_no: str, admin_id: int
    ) -> OrderResponse:
        """A5 对公转账：管理员确认到账并开通（复用支付回调链路，pay_type=2）"""
        order = (
            self.db.query(Order)
            .filter(Order.order_no == order_no, Order.is_deleted == 0)
            .first()
        )
        if not order:
            raise NotFoundError("订单不存在")
        if order.pay_status == PayStatus.PAID:
            raise ConflictError("订单已支付，请勿重复确认")

        from backend.domain.order.schemas import OrderPayCallback

        callback = OrderPayCallback(
            order_no=order.order_no,
            trade_no=trade_no or f"BANK-{order.order_no}",
            pay_type=2,  # 对公转账
            amount=Decimal(str(order.amount)),
        )
        result = self.handle_payment_callback(callback)

        from backend.domain.admin.services.system_service import AdminSystemService

        AdminSystemService(self.db).write_operation_log(
            admin_id=admin_id,
            module="order",
            operation="confirm_transfer",
            content=f"对公转账确认到账: {order_no}, 流水={callback.trade_no}",
        )
        return result

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
                Order.type.in_(
                    [
                        OrderType.QUARTERLY,
                        OrderType.SEMI_ANNUAL,
                        OrderType.OFFICIAL_MEMBER,
                    ]
                ),
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
        remaining_days = max(0, (child.member_expire_time - datetime.now()).days)

        options = []
        # 计算当前剩余价值（F16：按当前周期订单实付金额，而非现价——现价会
        # 在折扣/多孩优惠后高估剩余价值，导致升级差价少收）
        current_price = current_order.amount
        remaining_value = (
            current_price
            * Decimal(str(remaining_days))
            / Decimal(str(current_total_days))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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
            options.append(
                {
                    "current_type": current_type,
                    "target_type": target_type,
                    "target_price": str(target_price),
                    "target_days": target_days,
                    "remaining_value": str(remaining_value),
                    "upgrade_price": str(
                        upgrade_price.quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                    ),
                }
            )

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
        """计算退款金额 — 前 refund_free_days 天全退，之后按实付×剩余天数比例（A4）"""
        order = self.order_repo.get_by_id_or_raise(order_id)
        if order.pay_status != PayStatus.PAID:
            raise ValidationError("订单未支付，无法退款")

        # 从配置读取天数
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
            return {
                "refund_amount": order.amount,
                "daily_rate": Decimal("0"),
                "used_amount": Decimal("0"),
                "total_days": 0,
            }

        used = max(0, min(used_days, total_days) - free_days)
        from decimal import ROUND_HALF_UP

        # 公式完整计算后取整，中间步骤不取整（与 refund/service.py 实际退款口径一致）
        used_amount_raw = order.amount / total_days * used
        refund = max(
            (order.amount - used_amount_raw).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            Decimal("0"),
        )
        daily_rate = (order.amount / total_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return {
            "refund_amount": refund,
            "daily_rate": daily_rate,
            "used_amount": (order.amount - refund).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            "total_days": total_days,
        }

    def cancel_order(self, order_id: int, user_id: int) -> OrderResponse:
        """取消未支付的订单"""
        # F-053：行锁 + 状态前置——先查后改竞态会把并发已 PAID 的订单覆盖为 CLOSED
        # （close_expired_orders 已是条件更新正确范本，cancel_order 为同类漏改）
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id, Order.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not order or order.user_id != user_id:
            raise ValidationError("订单不存在")
        if order.pay_status != PayStatus.PENDING:
            raise ValidationError("仅可取消未支付的订单")
        order.pay_status = PayStatus.CLOSED
        self.db.commit()
        self.db.refresh(order)
        return OrderResponse.model_validate(order)
