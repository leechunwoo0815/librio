# backend/domain/activity/service.py
"""活动域业务逻辑"""

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from backend.common.exceptions import ConflictError, NotFoundError, ValidationError
from backend.domain.activity.models import Activity, ActivityEnrollment
from backend.domain.activity.repository import (
    ActivityRepository,
    ActivityEnrollmentRepository,
)
from backend.domain.activity.schemas import ActivityResponse, ActivityEnrollRequest

logger = logging.getLogger(__name__)


class ActivityService:
    def __init__(self, db: Session):
        self.db = db
        self.activity_repo = ActivityRepository(db)
        self.enrollment_repo = ActivityEnrollmentRepository(db)

    def list_activities(
        self, page: int = 1, page_size: int = 20
    ) -> list[ActivityResponse]:
        offset = (page - 1) * page_size
        activities = self.activity_repo.list_all(limit=page_size, offset=offset)
        return [ActivityResponse.model_validate(a) for a in activities]

    def list_with_count(self, page: int = 1, page_size: int = 20) -> dict:
        items = self.list_activities(page=page, page_size=page_size)
        total = self.activity_repo.count()
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
        }

    def get_activity(self, activity_id: int) -> ActivityResponse:
        return ActivityResponse.model_validate(
            self.activity_repo.get_by_id_or_raise(activity_id)
        )

    def enroll(self, data: ActivityEnrollRequest) -> dict:
        activity = self.activity_repo.get_by_id_or_raise(data.activity_id)

        # 检查活动状态
        if activity.status != Activity.STATUS_ENROLLING:
            raise ValidationError("该活动不在报名中")

        # 检查是否已报名
        existing = (
            self.db.query(ActivityEnrollment)
            .filter(
                ActivityEnrollment.child_id == data.child_id,
                ActivityEnrollment.activity_id == data.activity_id,
                ActivityEnrollment.is_deleted == 0,
            )
            .first()
        )
        if existing and existing.status != ActivityEnrollment.STATUS_CANCELLED:
            return {"status": "already_enrolled", "ticket_code": existing.ticket_code}

        # 原子递增 + 人数检查（防止并发超卖）
        if activity.max_participants:
            updated = (
                self.db.query(Activity)
                .filter(
                    Activity.id == data.activity_id,
                    Activity.current_participants < Activity.max_participants,
                )
                .update(
                    {Activity.current_participants: Activity.current_participants + 1}
                )
            )
            if not updated:
                raise ValidationError("报名人数已满")
        else:
            updated = (
                self.db.query(Activity)
                .filter(Activity.id == data.activity_id)
                .update(
                    {Activity.current_participants: Activity.current_participants + 1}
                )
            )

        ticket_code = f"ACT-{uuid.uuid4().hex[:8].upper()}"
        enrollment = ActivityEnrollment(
            child_id=data.child_id,
            activity_id=data.activity_id,
            ticket_code=ticket_code,
        )
        # 免费活动自动通过，收费活动待审核（需付费后通过）
        if activity.is_free:
            enrollment.status = ActivityEnrollment.STATUS_APPROVED
        self.enrollment_repo.create(enrollment)

        self.db.commit()
        logger.info(
            f"Activity enrollment: child={data.child_id}, activity={data.activity_id}"
        )
        return {"status": "enrolled", "ticket_code": ticket_code}

    def cancel_enrollment(self, enrollment_id: int) -> dict:
        """取消报名 — 活动开始前 N 小时可取消（从配置读取）"""
        from backend.common.config_service import ConfigService

        enrollment = (
            self.db.query(ActivityEnrollment)
            .filter(
                ActivityEnrollment.id == enrollment_id,
                ActivityEnrollment.is_deleted == 0,
            )
            .with_for_update()
            .first()
        )
        if not enrollment:
            raise NotFoundError("报名记录不存在")
        if enrollment.status == ActivityEnrollment.STATUS_CANCELLED:
            raise ConflictError("已取消")

        # 校验活动开始时间
        cancel_hours = ConfigService.get_int(self.db, "activity_cancel_hours", 24)
        activity = self.activity_repo.get_by_id(enrollment.activity_id)
        if activity and activity.start_time:
            hours_until_start = (
                activity.start_time - datetime.now()
            ).total_seconds() / 3600
            if hours_until_start < cancel_hours:
                raise ValidationError(f"活动开始前{cancel_hours}小时内不可取消")

        enrollment.status = ActivityEnrollment.STATUS_CANCELLED
        self.enrollment_repo.update(enrollment)

        # 释放名额
        if activity:
            activity.current_participants = max(
                0, (activity.current_participants or 0) - 1
            )
            self.activity_repo.update(activity)

        self.db.commit()
        logger.info(f"Enrollment cancelled: id={enrollment_id}")
        return {"id": enrollment.id, "status": enrollment.status}

    def get_enrollment_by_id(self, enrollment_id: int):
        enrollment = self.enrollment_repo.get_by_id(enrollment_id)
        if not enrollment:
            raise NotFoundError("报名记录不存在")
        return enrollment

    def sign_in(self, enrollment_id: int) -> dict:
        """签到 — 已通过的报名才能签到"""
        enrollment = self.enrollment_repo.get_by_id(enrollment_id)
        if not enrollment:
            raise NotFoundError("报名记录不存在")
        if enrollment.status not in (
            ActivityEnrollment.STATUS_APPROVED,
            ActivityEnrollment.STATUS_PENDING,
        ):
            raise ConflictError("当前状态不可签到")

        # 检查活动状态
        activity = self.activity_repo.get_by_id(enrollment.activity_id)
        if activity and activity.status != Activity.STATUS_IN_PROGRESS:
            raise ValidationError("活动未在进行中，不可签到")

        enrollment.status = ActivityEnrollment.STATUS_SIGNED_IN
        enrollment.sign_in_time = datetime.now()
        self.enrollment_repo.update(enrollment)
        self.db.commit()
        logger.info(f"Enrollment signed in: id={enrollment_id}")
        return {"id": enrollment.id, "status": enrollment.status}

    def sign_in_by_ticket_code(self, ticket_code: str) -> dict:
        """管理员通过票码（二维码）签到 — 用于活动签到页扫描"""
        enrollment = self.enrollment_repo.get_by_field("ticket_code", ticket_code)
        if not enrollment:
            raise NotFoundError("签到码对应的报名记录不存在")
        if enrollment.status == ActivityEnrollment.STATUS_CANCELLED:
            raise ConflictError("报名已取消，不可签到")
        if enrollment.status == ActivityEnrollment.STATUS_SIGNED_IN:
            return {
                "id": enrollment.id,
                "status": enrollment.status,
                "message": "已签到",
            }

        if enrollment.status not in (
            ActivityEnrollment.STATUS_APPROVED,
            ActivityEnrollment.STATUS_PENDING,
        ):
            raise ConflictError("当前报名状态不可签到")

        enrollment.status = ActivityEnrollment.STATUS_SIGNED_IN
        enrollment.sign_in_time = datetime.now()
        self.enrollment_repo.update(enrollment)
        self.db.commit()
        logger.info(f"Enrollment signed in by ticket code: {ticket_code}")
        return {"id": enrollment.id, "status": enrollment.status}

    def get_enrollments(self, activity_id: int) -> list:
        """获取活动报名列表"""
        from backend.domain.child.models import Child
        from backend.domain.user.models import User

        enrollments = (
            self.db.query(ActivityEnrollment)
            .filter(
                ActivityEnrollment.activity_id == activity_id,
                ActivityEnrollment.is_deleted == 0,
            )
            .all()
        )

        child_ids = [e.child_id for e in enrollments]
        children = {
            c.id: c for c in self.db.query(Child).filter(Child.id.in_(child_ids)).all()
        }
        user_ids = [c.user_id for c in children.values() if c.user_id]
        users = (
            {u.id: u for u in self.db.query(User).filter(User.id.in_(user_ids)).all()}
            if user_ids
            else {}
        )

        results = []
        for e in enrollments:
            child = children.get(e.child_id)
            user = users.get(child.user_id) if child and child.user_id else None
            results.append(
                {
                    "id": e.id,
                    "child_id": e.child_id,
                    "child_name": child.name if child else "未知",
                    "english_name": child.english_name if child else "",
                    "parent_name": user.parent_name if user else None,
                    "parent_phone": user.phone if user else None,
                    "status": e.status,
                    "ticket_code": e.ticket_code,
                    "checked_in": e.status == ActivityEnrollment.STATUS_SIGNED_IN,
                    "sign_in_time": e.sign_in_time.isoformat()
                    if e.sign_in_time
                    else None,
                }
            )
        return results

    def batch_checkin(self, activity_id: int, child_ids: list) -> dict:
        """批量签到"""
        enrollments = {
            e.child_id: e
            for e in self.db.query(ActivityEnrollment)
            .filter(
                ActivityEnrollment.activity_id == activity_id,
                ActivityEnrollment.child_id.in_(child_ids),
                ActivityEnrollment.is_deleted == 0,
            )
            .all()
        }
        success = 0
        errors = []
        for child_id in child_ids:
            enrollment = enrollments.get(child_id)
            if not enrollment:
                errors.append({"child_id": child_id, "error": "未找到报名记录"})
                continue
            if enrollment.status == ActivityEnrollment.STATUS_SIGNED_IN:
                continue  # 已签到，跳过
            enrollment.status = ActivityEnrollment.STATUS_SIGNED_IN
            enrollment.sign_in_time = datetime.now()
            self.enrollment_repo.update(enrollment)
            success += 1

        self.db.commit()
        return {"signed_count": success, "total": len(child_ids), "errors": errors}

    def confirm_paid_enrollment(self, enrollment_id: int) -> dict:
        """收费活动支付回调确认 — 将 PENDING 报名改为 APPROVED"""
        enrollment = self.enrollment_repo.get_by_id(enrollment_id)
        if not enrollment:
            raise NotFoundError("报名记录不存在")
        if enrollment.status != ActivityEnrollment.STATUS_PENDING:
            raise ConflictError(f"报名状态({enrollment.status})不允许确认")

        enrollment.status = ActivityEnrollment.STATUS_APPROVED
        self.enrollment_repo.update(enrollment)
        self.db.commit()
        logger.info(f"Paid enrollment confirmed: id={enrollment_id}")
        return {"id": enrollment.id, "status": enrollment.status}

    def cancel_activity(self, activity_id: int, admin_id: int) -> dict:
        """组织者取消活动 — 通知所有报名者 + 付费用户标记退款"""
        from backend.domain.child.models import Child

        activity = (
            self.db.query(Activity)
            .filter(Activity.id == activity_id, Activity.is_deleted == 0)
            .with_for_update()
            .first()
        )
        if not activity:
            raise NotFoundError("活动不存在")
        if activity.status == Activity.STATUS_CANCELLED:
            raise ConflictError("活动已取消")
        if activity.status == Activity.STATUS_FINISHED:
            raise ConflictError("活动已结束，无法取消")

        # 更新活动状态
        activity.status = Activity.STATUS_CANCELLED
        self.activity_repo.update(activity)

        # 获取所有有效报名（非取消）
        enrollments = (
            self.db.query(ActivityEnrollment)
            .filter(
                ActivityEnrollment.activity_id == activity_id,
                ActivityEnrollment.status.in_(
                    [
                        ActivityEnrollment.STATUS_PENDING,
                        ActivityEnrollment.STATUS_APPROVED,
                    ]
                ),
                ActivityEnrollment.is_deleted == 0,
            )
            .all()
        )

        child_ids = [e.child_id for e in enrollments]
        children = {
            c.id: c for c in self.db.query(Child).filter(Child.id.in_(child_ids)).all()
        }

        cancelled_count = 0
        refund_count = 0
        for e in enrollments:
            e.status = ActivityEnrollment.STATUS_CANCELLED
            self.enrollment_repo.update(e)
            cancelled_count += 1

            child = children.get(e.child_id)
            # 收费活动报名 → 写退款申请
            if child and not activity.is_free and activity.price and activity.price > 0:
                eid = e.id
                try:
                    from backend.domain.refund.models import RefundApplication
                    from backend.common.base_repo import BaseRepository

                    refund = RefundApplication(
                        order_id=None,  # 活动退款无关联订单
                        user_id=child.user_id,
                        child_id=e.child_id,
                        refund_amount=activity.price,
                        used_days=0,
                        reason=f"活动「{activity.title}」被组织者取消，自动退款",
                    )
                    refund_repo = BaseRepository(self.db, RefundApplication)
                    refund_repo.create(refund)
                    refund_count += 1
                except Exception as ex:
                    logger.warning(f"Auto refund failed for enrollment {eid}: {ex}")

            # 发送通知
            try:
                if child:
                    from backend.domain.message.models import SystemMessage

                    msg = SystemMessage(
                        user_id=child.user_id,
                        title="活动取消通知",
                        content=f"活动「{activity.title}」已被取消。{'退款将自动处理，请留意。' if not activity.is_free else ''}",
                        msg_type=5,
                        priority=1,
                    )
                    self.db.add(msg)
            except Exception as ex:
                logger.warning(f"Notification failed for enrollment {e.id}: {ex}")

        self.db.commit()
        logger.info(
            f"Activity cancelled: id={activity_id}, enrollments={cancelled_count}, refunds={refund_count}"
        )
        return {
            "activity_id": activity_id,
            "cancelled_enrollments": cancelled_count,
            "refund_applications": refund_count,
        }

    def create_activity(self, data) -> dict:
        """创建活动"""
        activity = Activity(**data.model_dump())
        created = self.activity_repo.create(activity)
        self.db.commit()
        return {"id": created.id, "message": "活动创建成功"}

    def update_activity(self, activity_id: int, data) -> dict:
        """更新活动"""
        from backend.common.exceptions import NotFoundError

        activity = self.activity_repo.get_by_id(activity_id)
        if not activity or activity.is_deleted == 1:
            raise NotFoundError("活动不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(activity, key):
                setattr(activity, key, value)
        self.activity_repo.update(activity)
        self.db.commit()
        return {"success": True, "message": "活动更新成功"}

    def delete_activity(self, activity_id: int) -> dict:
        """删除活动"""
        from backend.common.exceptions import NotFoundError

        activity = self.activity_repo.get_by_id(activity_id)
        if not activity or activity.is_deleted == 1:
            raise NotFoundError("活动不存在")
        activity.is_deleted = 1
        self.activity_repo.update(activity)
        self.db.commit()
        return {"success": True, "message": "活动已删除"}
