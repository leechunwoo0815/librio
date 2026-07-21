# backend/domain/child/service.py
"""孩子域业务逻辑 — 会员状态、权益转让、借书权限"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.common.exceptions import ForbiddenError, NotFoundError, ValidationError
from backend.common.types import DepositStatus, MemberStatus
from backend.domain.child.benefit_transfer_model import BenefitTransferApplication
from backend.domain.child.models import Child
from backend.domain.child.repository import ChildRepository
from backend.domain.child.schemas import (
    ChildCreate,
    ChildResponse,
    ChildStatusUpdate,
    ChildUpdate,
)

logger = logging.getLogger(__name__)


def assert_no_pending_transfer(db: Session, source_child_id: int) -> None:
    """校验孩子无审核中或已通过的权益转让记录

    用于在借书/预约/退款/续费等入口前拦截，防止转让期间操作。
    不拦截 REJECTED 记录或软删除记录。
    """
    from backend.domain.child.benefit_transfer_model import BenefitTransferApplication
    from backend.common.exceptions import ValidationError

    approved = (
        db.query(BenefitTransferApplication)
        .filter(
            BenefitTransferApplication.source_child_id == source_child_id,
            BenefitTransferApplication.status == 1,
            BenefitTransferApplication.is_deleted == 0,
        )
        .first()
    )
    if approved:
        raise ValidationError("该孩子已有审核通过的权益转让记录，无法继续")

    approved_as_target = (
        db.query(BenefitTransferApplication)
        .filter(
            BenefitTransferApplication.target_child_id == source_child_id,
            BenefitTransferApplication.status == 1,
            BenefitTransferApplication.is_deleted == 0,
        )
        .first()
    )
    if approved_as_target:
        raise ValidationError("该孩子已有审核通过的权益转让记录，无法继续")

    pending = (
        db.query(BenefitTransferApplication)
        .filter(
            BenefitTransferApplication.source_child_id == source_child_id,
            BenefitTransferApplication.status == 0,
            BenefitTransferApplication.is_deleted == 0,
        )
        .first()
    )
    if pending:
        raise ValidationError(
            f"该孩子有审核中的转让申请（申请ID={pending.id}），请等待审核完成"
        )


class ChildService:
    """孩子服务

    架构意图：
      - 会员状态迁移是有向图的，不是任意切换
      - 权益转让在同一事务内完成（source + target 同 commit）
      - 借书权限检查仅看会员状态 + 押金状态
    """

    def __init__(self, db: Session):
        self.db = db
        self.child_repo = ChildRepository(db)

    # ============================================================
    # 会员状态迁移图
    # TRIAL → OBSERVATION → OFFICIAL → EXPIRED → OFFICIAL (可循环)
    # 任何状态 → EXITED (不可逆)
    # ============================================================
    ALLOWED_TRANSITIONS: dict[int, list[int]] = {
        MemberStatus.TRIAL: [
            MemberStatus.OBSERVATION,
            MemberStatus.OFFICIAL,
            MemberStatus.EXITED,
        ],
        MemberStatus.OBSERVATION: [MemberStatus.OFFICIAL, MemberStatus.EXITED],
        MemberStatus.OFFICIAL: [MemberStatus.EXPIRED, MemberStatus.EXITED],
        MemberStatus.EXPIRED: [MemberStatus.OFFICIAL, MemberStatus.EXITED],
        MemberStatus.EXITED: [],
    }

    def create_child(self, user_id: int, child_data: ChildCreate) -> ChildResponse:
        """为孩子创建档案"""
        child = Child(
            user_id=user_id,
            name=child_data.name,
            english_name=child_data.english_name,
            age=child_data.age,
            grade=child_data.grade,
            venue_id=child_data.venue_id,
        )
        created = self.child_repo.create(child)
        self.db.commit()
        logger.info(f"Child created: id={created.id}, user_id={user_id}")
        return ChildResponse.model_validate(created)

    def get_child(self, child_id: int) -> ChildResponse:
        """获取孩子详情"""
        child = self.child_repo.get_by_id_or_raise(child_id)
        return ChildResponse.model_validate(child)

    def get_user_children(self, user_id: int) -> list[ChildResponse]:
        """获取用户的所有孩子"""
        children = self.child_repo.get_by_user_id(user_id)
        return [ChildResponse.model_validate(c) for c in children]

    def update_child(self, child_id: int, update_data: ChildUpdate) -> ChildResponse:
        """更新孩子基本信息"""
        child = self.child_repo.get_by_id_or_raise(child_id)
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(child, field, value)
        self.child_repo.update(child)
        self.db.commit()
        return ChildResponse.model_validate(child)

    def update_status(
        self, child_id: int, status_data: ChildStatusUpdate
    ) -> ChildResponse:
        """更新会员状态 — 校验迁移合法性"""
        child = (
            self.db.query(Child)
            .filter(Child.id == child_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not child:
            raise NotFoundError("孩子不存在")

        old_status = child.status
        new_status = status_data.status
        allowed = self.ALLOWED_TRANSITIONS.get(old_status, [])

        if new_status not in allowed:
            raise ValidationError(
                f"状态迁移不合法: {old_status} → {new_status}，允许的迁移: {allowed}"
            )

        child.status = new_status
        if status_data.member_start_time is not None:
            child.member_start_time = status_data.member_start_time
        if status_data.member_expire_time is not None:
            child.member_expire_time = status_data.member_expire_time

        self.child_repo.update(child)
        self.db.commit()
        logger.info(f"Child {child_id} status changed: {old_status} -> {new_status}")
        return ChildResponse.model_validate(child)

    def _validate_transfer(self, source_id: int, target_id: int) -> tuple:
        """校验转让合法性，返回 (source, target)"""
        source = (
            self.db.query(Child)
            .filter(Child.id == source_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        target = (
            self.db.query(Child)
            .filter(Child.id == target_id, Child.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not source or not target:
            raise NotFoundError("孩子不存在")

        if source.user_id != target.user_id:
            raise ForbiddenError("只能在同一用户的孩子间转让")

        if source.status not in (MemberStatus.OBSERVATION, MemberStatus.OFFICIAL):
            raise ValidationError("源孩子状态不允许转让")

        if target.status == MemberStatus.EXITED:
            raise ForbiddenError("目标孩子已退出，无法转让权益")

        if target.status in (
            MemberStatus.OBSERVATION,
            MemberStatus.OFFICIAL,
            MemberStatus.EXPIRED,
        ):
            raise ForbiddenError("目标孩子已有会员权益，无法转让")

        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus

        active_borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == source_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )
        if active_borrows > 0:
            raise ValidationError(f"源孩子有 {active_borrows} 本未还书，请先归还")

        if source.outstanding_fines and source.outstanding_fines > 0:
            raise ValidationError(
                f"源孩子有未缴罚款 {source.outstanding_fines} 元，请先结清"
            )

        # 目标孩子校验：无活跃借阅 + 无未缴罚款
        target_active_borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == target_id,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
                BorrowRecord.is_deleted == 0,
            )
            .count()
        )
        if target_active_borrows > 0:
            raise ValidationError(f"目标孩子有 {target_active_borrows} 本未还书")

        if target.outstanding_fines and target.outstanding_fines > 0:
            raise ValidationError(f"目标孩子有未缴罚款 {target.outstanding_fines} 元")

        return source, target

    def transfer_benefit(self, source_id: int, target_id: int) -> dict:
        """权益转让 — 仅限同一用户的孩子（管理员审核通过后调用）"""
        source, target = self._validate_transfer(source_id, target_id)

        old_status = source.status
        target.status = old_status
        target.member_start_time = source.member_start_time
        target.member_expire_time = source.member_expire_time
        source.status = MemberStatus.EXPIRED
        source.member_start_time = None
        source.member_expire_time = None

        self.child_repo.update(source)
        self.child_repo.update(target)
        self.db.commit()
        logger.info(
            f"Benefit transferred: {source_id} -> {target_id}, status={old_status}"
        )
        return {"success": True, "transferred_status": old_status}

    def create_benefit_transfer_application(
        self, source_child_id: int, target_child_id: int, user_id: int
    ) -> dict:
        assert_no_pending_transfer(self.db, source_child_id)
        self._validate_transfer(source_child_id, target_child_id)
        application = BenefitTransferApplication(
            source_child_id=source_child_id,
            target_child_id=target_child_id,
            user_id=user_id,
            status=0,
            remark="",
            create_time=datetime.now(),
            update_time=datetime.now(),
        )
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        return {
            "application_id": application.id,
            "status": 0,
            "message": "申请已提交，等待管理员审核",
        }

    def get_transfer_records(self, user_id: int) -> list[dict]:
        from backend.domain.child.models import Child

        apps = (
            self.db.query(BenefitTransferApplication)
            .filter(
                BenefitTransferApplication.user_id == user_id,
                BenefitTransferApplication.is_deleted == 0,
            )
            .order_by(BenefitTransferApplication.create_time.desc())
            .all()
        )
        child_ids = {app.source_child_id for app in apps} | {
            app.target_child_id for app in apps
        }
        children = {
            c.id: c for c in self.db.query(Child).filter(Child.id.in_(child_ids)).all()
        }
        status_map = {0: "pending", 1: "approved", 2: "rejected"}
        result = []
        for app in apps:
            src = children.get(app.source_child_id)
            tgt = children.get(app.target_child_id)
            result.append(
                {
                    "id": app.id,
                    "source_child_name": src.name if src else "--",
                    "target_child_name": tgt.name if tgt else "--",
                    "status": status_map.get(app.status, "pending"),
                    "created_at": app.create_time.isoformat()
                    if app.create_time
                    else "",
                }
            )
        return result

    def delete_child(self, child_id: int, user_id: int) -> dict:
        from backend.domain.borrow.models import BorrowRecord
        from backend.common.types import BorrowStatus

        child = self.child_repo.get_by_id(child_id)
        if not child or child.is_deleted == 1:
            raise NotFoundError("孩子不存在")
        if child.user_id != user_id:
            raise ForbiddenError("无权操作该孩子")

        active_borrows = (
            self.db.query(BorrowRecord)
            .filter(
                BorrowRecord.child_id == child_id,
                BorrowRecord.is_deleted == 0,
                BorrowRecord.status.in_([BorrowStatus.BORROWING, BorrowStatus.OVERDUE]),
            )
            .count()
        )
        if active_borrows > 0:
            raise ValidationError(
                f"该孩子有 {active_borrows} 本未还书，请先归还后再删除"
            )

        child.soft_delete()
        self.db.commit()
        return {"success": True, "message": "孩子已删除"}

    def can_borrow_books(self, child_id: int) -> bool:
        """检查孩子是否可借书 — 会员状态 + 押金状态"""
        child = self.child_repo.get_by_id_or_raise(child_id)
        return (
            child.status in (MemberStatus.OBSERVATION, MemberStatus.OFFICIAL)
            and child.deposit_status == DepositStatus.PAID
        )

    def update_reading_stats(
        self, child_id: int, words: int = 0, minutes: int = 0, books: int = 0
    ) -> None:
        """更新阅读统计（事件处理器调用）"""
        child = self.child_repo.get_by_id(child_id)
        if not child:
            return
        if words:
            child.total_words_read = (child.total_words_read or 0) + words
        if minutes:
            child.total_reading_minutes = (child.total_reading_minutes or 0) + minutes
        if books:
            child.total_books_finished = (child.total_books_finished or 0) + books
        self.child_repo.update(child)
        # 不 commit，由调用方控制事务

    def update_streak(self, child_id: int, streak_days: int) -> None:
        """更新连续打卡天数（事件处理器调用）"""
        child = self.child_repo.get_by_id(child_id)
        if not child:
            return
        child.current_streak_days = streak_days
        if streak_days > (child.longest_streak_days or 0):
            child.longest_streak_days = streak_days
        self.child_repo.update(child)
