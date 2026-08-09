# backend/domain/parent_course_time/service.py
"""亲子课时间段业务逻辑"""

import logging

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.parent_course_time.models import ParentCourseTime
from backend.domain.parent_course_time.schemas import (
    ParentCourseTimeCreate,
    ParentCourseTimeResponse,
    ParentCourseTimeUpdate,
)

logger = logging.getLogger(__name__)


class ParentCourseTimeService:
    """亲子课时间段服务"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = BaseRepository(db, ParentCourseTime)

    def list_by_venue(self, venue_id: int) -> list[ParentCourseTimeResponse]:
        """用户端 — 列出场馆可选时间段"""
        records = (
            self.db.query(ParentCourseTime)
            .filter(
                ParentCourseTime.venue_id == venue_id,
                ParentCourseTime.status == 1,  # 仅可预约
                ParentCourseTime.is_deleted == 0,
            )
            .order_by(ParentCourseTime.course_date, ParentCourseTime.start_time)
            .all()
        )
        return [ParentCourseTimeResponse.model_validate(r) for r in records]

    def list_all(self, venue_id: int | None = None) -> list[ParentCourseTimeResponse]:
        """管理端 — 列出所有时间段"""
        q = self.db.query(ParentCourseTime).filter(
            ParentCourseTime.is_deleted == 0,
        )
        if venue_id is not None:
            q = q.filter(ParentCourseTime.venue_id == venue_id)
        records = q.order_by(
            ParentCourseTime.course_date.desc(), ParentCourseTime.start_time
        ).all()
        return [ParentCourseTimeResponse.model_validate(r) for r in records]

    def create(self, data: ParentCourseTimeCreate) -> ParentCourseTimeResponse:
        """创建时间段"""
        # F-069：时间校验——结束必须晚于开始
        if data.end_time <= data.start_time:
            from backend.common.exceptions import ValidationError

            raise ValidationError("结束时间必须晚于开始时间")
        # F-069 终审：同日同 venue 时间重叠校验（双时段不能同时占同一个亲子课教室）
        self._assert_no_overlap(
            venue_id=data.venue_id,
            course_date=data.course_date,
            start_time=data.start_time,
            end_time=data.end_time,
            exclude_id=None,
        )
        record = ParentCourseTime(
            venue_id=data.venue_id,
            course_date=data.course_date,
            start_time=data.start_time,
            end_time=data.end_time,
            max_participants=data.max_participants,
        )
        created = self.repo.create(record)
        self.db.commit()
        logger.info(
            f"ParentCourseTime created: id={created.id}, venue={data.venue_id}, "
            f"date={data.course_date}"
        )
        return ParentCourseTimeResponse.model_validate(created)

    def update(
        self, slot_id: int, data: ParentCourseTimeUpdate
    ) -> ParentCourseTimeResponse:
        """更新时间段"""
        record = self.repo.get_by_id_or_raise(slot_id)
        update_data = data.model_dump(exclude_unset=True)
        # F-069：合并后时间校验
        end = update_data.get("end_time", record.end_time)
        start = update_data.get("start_time", record.start_time)
        if end <= start:
            from backend.common.exceptions import ValidationError

            raise ValidationError("结束时间必须晚于开始时间")
        self._assert_no_overlap(
            venue_id=update_data.get("venue_id", record.venue_id),
            course_date=update_data.get("course_date", record.course_date),
            start_time=start,
            end_time=end,
            exclude_id=slot_id,
        )
        for key, value in update_data.items():
            setattr(record, key, value)
        self.repo.update(record)
        self.db.commit()
        return ParentCourseTimeResponse.model_validate(record)

    def _assert_no_overlap(
        self,
        venue_id: int,
        course_date,
        start_time,
        end_time,
        exclude_id: int | None,
    ) -> None:
        """同日同 venue 区间重叠检查（[start,end) 半开区间相交判定）"""
        from backend.common.exceptions import ValidationError

        query = self.db.query(ParentCourseTime).filter(
            ParentCourseTime.venue_id == venue_id,
            ParentCourseTime.course_date == course_date,
            ParentCourseTime.is_deleted == 0,
            ParentCourseTime.start_time < end_time,
            ParentCourseTime.end_time > start_time,
        )
        if exclude_id is not None:
            query = query.filter(ParentCourseTime.id != exclude_id)
        if query.first():
            raise ValidationError("同一天同一场馆已存在时间重叠的亲子课时段")

    def delete(self, slot_id: int) -> dict:
        """删除时间段（软删除）"""
        from backend.common.exceptions import ConflictError
        from backend.domain.order.models import Order

        record = self.repo.get_by_id_or_raise(slot_id)
        # F-112：已付费/待支付亲子课订单关联该时段 → 拒绝删除（家长订单悬空无退款无通知）
        linked_orders = (
            self.db.query(Order)
            .filter(
                Order.parent_course_time_id == slot_id,
                Order.pay_status.in_([1, 0]),  # PAID/PENDING
                Order.is_deleted == 0,
            )
            .count()
        )
        if linked_orders > 0:
            raise ConflictError(
                f"该时段有 {linked_orders} 笔关联订单，请先处理订单/退款后再删除"
            )
        record.is_deleted = 1
        self.repo.update(record)
        self.db.commit()
        logger.info(f"ParentCourseTime deleted: id={slot_id}")
        return {"success": True, "id": slot_id}

    def get(self, slot_id: int) -> ParentCourseTimeResponse:
        """获取单个时间段"""
        record = self.repo.get_by_id_or_raise(slot_id)
        return ParentCourseTimeResponse.model_validate(record)
