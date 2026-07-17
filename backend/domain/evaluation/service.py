# backend/domain/evaluation/service.py
"""测评域业务逻辑 — AR测评、观察期评价、指导记录"""

import logging

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.evaluation.models import (
    AREvaluation,
    ObservationEvaluation,
    GuidanceRecord,
)
from backend.domain.evaluation.schemas import (
    AREvaluationCreate,
    AREvaluationResponse,
)

logger = logging.getLogger(__name__)


class EvaluationService:
    """测评服务"""

    def __init__(self, db: Session):
        self.db = db
        self.ar_repo = BaseRepository(db, AREvaluation)
        self.obs_eval_repo = BaseRepository(db, ObservationEvaluation)
        self.guidance_repo = BaseRepository(db, GuidanceRecord)

    # ==================== AR测评 ====================

    def create_ar_evaluation(self, data: AREvaluationCreate) -> AREvaluationResponse:
        """创建 AR 测评记录，同时更新孩子的 ar_level"""
        from backend.domain.child.models import Child

        record = AREvaluation(
            child_id=data.child_id,
            ar_level=data.ar_level,
            evaluation_date=data.evaluation_date,
            teacher_id=data.teacher_id,
            remark=data.remark,
        )
        created = self.ar_repo.create(record)

        # 同步更新孩子的当前 AR 级别
        child = (
            self.db.query(Child)
            .filter(Child.id == data.child_id, Child.is_deleted == 0)
            .first()
        )
        if child:
            child.ar_level = data.ar_level

        self.db.commit()
        logger.info(
            f"AR evaluation created: child={data.child_id}, ar_level={data.ar_level}"
        )
        return AREvaluationResponse.model_validate(created)

    def get_ar_evaluations(self, child_id: int) -> list[AREvaluationResponse]:
        """获取孩子的 AR 测评历史"""
        records = (
            self.db.query(AREvaluation)
            .filter(
                AREvaluation.child_id == child_id,
                AREvaluation.is_deleted == 0,
            )
            .order_by(AREvaluation.evaluation_date.desc())
            .all()
        )
        return [AREvaluationResponse.model_validate(r) for r in records]

    def get_latest_ar_evaluation(self, child_id: int) -> AREvaluationResponse | None:
        """获取最近一次 AR 测评"""
        record = (
            self.db.query(AREvaluation)
            .filter(
                AREvaluation.child_id == child_id,
                AREvaluation.is_deleted == 0,
            )
            .order_by(AREvaluation.evaluation_date.desc())
            .first()
        )
        if not record:
            return None
        return AREvaluationResponse.model_validate(record)
