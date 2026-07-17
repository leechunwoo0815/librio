import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.common.exceptions import ValidationError
from backend.domain.child.benefit_transfer_model import BenefitTransferApplication
from backend.domain.child.service import ChildService

logger = logging.getLogger(__name__)


class BenefitTransferAdminService:
    def __init__(self, db: Session):
        self.db = db

    def get_list(
        self, status: int | None = None, page: int = 1, page_size: int = 20
    ) -> dict:
        query = self.db.query(BenefitTransferApplication).filter(
            BenefitTransferApplication.is_deleted == 0
        )
        if status is not None:
            query = query.filter(BenefitTransferApplication.status == status)
        total = query.count()
        items = (
            query.order_by(BenefitTransferApplication.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        from backend.domain.user.models import User
        from backend.domain.child.models import Child

        source_ids = {app.source_child_id for app in items}
        target_ids = {app.target_child_id for app in items}
        user_ids = {app.user_id for app in items}
        all_child_ids = source_ids | target_ids
        children = {
            c.id: c
            for c in self.db.query(Child).filter(Child.id.in_(all_child_ids)).all()
        }
        users = {
            u.id: u for u in self.db.query(User).filter(User.id.in_(user_ids)).all()
        }
        result = []
        for app in items:
            source_child = children.get(app.source_child_id)
            target_child = children.get(app.target_child_id)
            user = users.get(app.user_id)
            result.append(
                {
                    "id": app.id,
                    "source_child_id": app.source_child_id,
                    "source_child_name": source_child.name if source_child else "--",
                    "target_child_id": app.target_child_id,
                    "target_child_name": target_child.name if target_child else "--",
                    "user_id": app.user_id,
                    "user_name": user.parent_name if user else "--",
                    "status": app.status,
                    "remark": app.remark or "",
                    "reviewed_at": app.reviewed_at.isoformat()
                    if app.reviewed_at
                    else None,
                    "reviewer_id": app.reviewer_id,
                    "review_remark": app.review_remark or "",
                    "create_time": app.create_time.isoformat()
                    if app.create_time
                    else None,
                }
            )

        return {"items": result, "total": total, "page": page, "page_size": page_size}

    def approve(
        self, application_id: int, reviewer_id: int, review_remark: str = ""
    ) -> dict:
        app = (
            self.db.query(BenefitTransferApplication)
            .filter(
                BenefitTransferApplication.id == application_id,
                BenefitTransferApplication.is_deleted == 0,
            )
            .first()
        )
        if not app:
            raise ValidationError("申请不存在")
        if app.status != 0:
            raise ValidationError("申请已处理，无法重复审核")

        child_service = ChildService(self.db)
        child_service.transfer_benefit(app.source_child_id, app.target_child_id)

        app.status = 1
        app.reviewer_id = reviewer_id
        app.review_remark = review_remark
        app.reviewed_at = func.now()
        self.db.commit()
        logger.info(
            f"Benefit transfer approved: application_id={application_id}, reviewer_id={reviewer_id}"
        )
        return {"success": True, "message": "审核通过，权益已转移"}

    def reject(
        self, application_id: int, reviewer_id: int, review_remark: str = ""
    ) -> dict:
        app = (
            self.db.query(BenefitTransferApplication)
            .filter(
                BenefitTransferApplication.id == application_id,
                BenefitTransferApplication.is_deleted == 0,
            )
            .first()
        )
        if not app:
            raise ValidationError("申请不存在")
        if app.status != 0:
            raise ValidationError("申请已处理，无法重复审核")

        app.status = 2
        app.reviewer_id = reviewer_id
        app.review_remark = review_remark
        app.reviewed_at = func.now()
        self.db.commit()
        logger.info(
            f"Benefit transfer rejected: application_id={application_id}, reviewer_id={reviewer_id}"
        )
        return {"success": True, "message": "已拒绝转让申请"}
