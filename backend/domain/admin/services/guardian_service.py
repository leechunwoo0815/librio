# backend/domain/admin/services/guardian_service.py
"""F1 账号迁移/监护人变更 + F5 退出复活 — 管理端服务"""

import logging

from sqlalchemy.orm import Session

from backend.common.exceptions import ConflictError, NotFoundError, ValidationError
from backend.common.types import MemberStatus
from backend.domain.child.models import Child
from backend.domain.user.models import User

logger = logging.getLogger(__name__)


class GuardianService:
    """监护人关系管理（管理员操作，全程操作日志）"""

    def __init__(self, db: Session):
        self.db = db

    def _log(self, admin_id: int, operation: str, content: str):
        from backend.domain.admin.services.system_service import AdminSystemService

        AdminSystemService(self.db).write_operation_log(
            admin_id=admin_id, module="guardian", operation=operation, content=content
        )

    def migrate_account(
        self, old_user_id: int, new_user_id: int, admin_id: int
    ) -> dict:
        """F1 账号迁移（换微信/openid 变更）：旧账号全部孩子及关联数据迁到新账号"""
        if old_user_id == new_user_id:
            raise ValidationError("源账号与目标账号相同")

        old_user = (
            self.db.query(User)
            .filter(User.id == old_user_id, User.is_deleted == 0)
            .first()
        )
        new_user = (
            self.db.query(User)
            .filter(User.id == new_user_id, User.is_deleted == 0)
            .first()
        )
        if not old_user or not new_user:
            raise NotFoundError("源账号或目标账号不存在")

        from backend.domain.order.models import Order
        from backend.domain.refund.models import RefundApplication
        from backend.domain.message.models import SystemMessage

        moved_children = (
            self.db.query(Child)
            .filter(Child.user_id == old_user_id, Child.is_deleted == 0)
            .update({Child.user_id: new_user_id}, synchronize_session="fetch")
        )
        moved_orders = (
            self.db.query(Order)
            .filter(Order.user_id == old_user_id, Order.is_deleted == 0)
            .update({Order.user_id: new_user_id}, synchronize_session="fetch")
        )
        moved_refunds = (
            self.db.query(RefundApplication)
            .filter(
                RefundApplication.user_id == old_user_id,
                RefundApplication.is_deleted == 0,
            )
            .update(
                {RefundApplication.user_id: new_user_id}, synchronize_session="fetch"
            )
        )
        moved_messages = (
            self.db.query(SystemMessage)
            .filter(SystemMessage.user_id == old_user_id, SystemMessage.is_deleted == 0)
            .update({SystemMessage.user_id: new_user_id}, synchronize_session="fetch")
        )

        self.db.commit()
        self._log(
            admin_id,
            "migrate_account",
            f"账号迁移: user {old_user_id} → {new_user_id}, "
            f"孩子{moved_children}/订单{moved_orders}/退款{moved_refunds}/消息{moved_messages}",
        )
        return {
            "success": True,
            "moved_children": moved_children,
            "moved_orders": moved_orders,
            "moved_refunds": moved_refunds,
            "moved_messages": moved_messages,
        }

    def change_guardian(
        self, child_id: int, new_user_id: int, confirmed: bool, admin_id: int
    ) -> dict:
        """F1 监护人变更（需 confirmed=true，线下双方确认后操作）"""
        if not confirmed:
            raise ValidationError("监护人变更需双方确认（confirmed=true）")

        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")
        new_user = (
            self.db.query(User)
            .filter(User.id == new_user_id, User.is_deleted == 0)
            .first()
        )
        if not new_user:
            raise NotFoundError("新监护人账号不存在")
        if child.user_id == new_user_id:
            raise ConflictError("孩子已属于该监护人")

        old_user_id = child.user_id
        child.user_id = new_user_id

        # 孩子维度的财务记录一并随迁
        from backend.domain.order.models import Order
        from backend.domain.refund.models import RefundApplication

        self.db.query(Order).filter(
            Order.child_id == child_id, Order.is_deleted == 0
        ).update({Order.user_id: new_user_id}, synchronize_session="fetch")
        self.db.query(RefundApplication).filter(
            RefundApplication.child_id == child_id, RefundApplication.is_deleted == 0
        ).update({RefundApplication.user_id: new_user_id}, synchronize_session="fetch")

        self.db.commit()
        self._log(
            admin_id,
            "change_guardian",
            f"监护人变更: child {child_id}（{child.name}）user {old_user_id} → {new_user_id}",
        )
        return {"success": True, "child_id": child_id, "new_user_id": new_user_id}

    def revive_child(self, child_id: int, admin_id: int) -> dict:
        """F5 复活：EXITED → TRIAL（历史阅读数据保留，权益清零重来）"""
        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")
        if child.status != MemberStatus.EXITED:
            raise ConflictError("仅已退出（EXITED）的孩子可复活")

        child.status = MemberStatus.TRIAL
        child.member_start_time = None
        child.member_expire_time = None
        self.db.commit()
        self._log(
            admin_id,
            "revive_child",
            f"孩子复活: child {child_id}（{child.name}）EXITED → TRIAL",
        )
        logger.info(f"Child revived: {child_id} EXITED→TRIAL by admin {admin_id}")
        return {
            "success": True,
            "child_id": child_id,
            "status": int(MemberStatus.TRIAL),
        }
