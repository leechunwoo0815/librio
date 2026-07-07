# backend/domain/child/service.py
"""孩子域业务逻辑 — 会员状态、权益转让、借书权限"""

import logging

from sqlalchemy.orm import Session

from backend.common.exceptions import ForbiddenError, ValidationError
from backend.common.types import DepositStatus, MemberStatus
from backend.domain.child.models import Child
from backend.domain.child.repository import ChildRepository
from backend.domain.child.schemas import (
    ChildCreate,
    ChildResponse,
    ChildStatusUpdate,
    ChildUpdate,
)

logger = logging.getLogger(__name__)


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
        child = self.child_repo.get_by_id_or_raise(child_id)

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

    def transfer_benefit(self, source_id: int, target_id: int) -> dict:
        """权益转让 — 仅限同一用户的孩子"""
        source = self.child_repo.get_by_id_or_raise(source_id)
        target = self.child_repo.get_by_id_or_raise(target_id)

        if source.user_id != target.user_id:
            raise ForbiddenError("只能在同一用户的孩子间转让")

        if source.status not in (MemberStatus.OBSERVATION, MemberStatus.OFFICIAL):
            raise ValidationError("源孩子状态不允许转让")

        if target.status == MemberStatus.EXITED:
            raise ForbiddenError("目标孩子已退出，无法转让权益")

        # P0-4: 目标孩子不能已是观察期/正式会员/过期（否则覆盖现有权益）
        if target.status in (MemberStatus.OBSERVATION, MemberStatus.OFFICIAL, MemberStatus.EXPIRED):
            raise ForbiddenError("目标孩子已有会员权益，无法转让")

        # 校验源孩子无未还书
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

        # 校验源孩子无未缴罚款
        if source.outstanding_fines and source.outstanding_fines > 0:
            raise ValidationError(
                f"源孩子有未缴罚款 {source.outstanding_fines} 元，请先结清"
            )

        # 执行转让
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
