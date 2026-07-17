# backend/domain/evaluation/router.py
"""测评域 API 路由 — AR测评"""

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_db
from backend.middleware.admin_rbac import require_perm
from backend.domain.evaluation.schemas import (
    AREvaluationCreate,
    AREvaluationResponse,
)
from backend.domain.evaluation.service import EvaluationService

router = APIRouter(prefix="/ar-evaluation", tags=["AR测评"])


# ============================================================
# 管理端
# ============================================================


@router.post("/", response_model=AREvaluationResponse, status_code=201)
def create_ar_evaluation(
    data: AREvaluationCreate,
    db=Depends(get_db),
    admin=Depends(require_perm("evaluation.create")),
):
    """管理员创建 AR 测评记录（亲子课结束后）"""
    service = EvaluationService(db)
    return service.create_ar_evaluation(data)


@router.get("/child/{child_id}", response_model=list[AREvaluationResponse])
def get_ar_evaluations(
    child_id: int,
    db=Depends(get_db),
    admin=Depends(require_perm("evaluation.list")),
):
    """管理员查看孩子的 AR 测评历史"""
    service = EvaluationService(db)
    return service.get_ar_evaluations(child_id)


@router.get("/child/{child_id}/latest", response_model=AREvaluationResponse | None)
def get_latest_ar_evaluation(
    child_id: int,
    db=Depends(get_db),
    admin=Depends(require_perm("evaluation.view")),
):
    """管理员查看最新 AR 测评"""
    service = EvaluationService(db)
    return service.get_latest_ar_evaluation(child_id)
