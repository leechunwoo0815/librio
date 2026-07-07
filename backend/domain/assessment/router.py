# backend/domain/assessment/router.py
"""评估域 API 路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import get_db
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN, ROLE_STAFF
from backend.domain.assessment.schemas import (
    AssessmentCreateRequest,
    AssessmentUpdateRequest,
    AssessmentResponse,
    AssessmentListResponse,
)
from backend.domain.assessment.service import AssessmentService

router = APIRouter(prefix="/admin/api/assessment", tags=["评估管理"])


@router.get("/list", response_model=AssessmentListResponse)
def list_assessments(
    keyword: str | None = None,
    status: str | None = None,
    venue_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取评估列表"""
    service = AssessmentService(db)
    return service.list_assessments(keyword, status, venue_id, page, page_size)


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: int,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取评估详情"""
    service = AssessmentService(db)
    return service.get_assessment(assessment_id)


@router.post("/", response_model=AssessmentResponse, status_code=201)
def create_assessment(
    data: AssessmentCreateRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """创建评估"""
    service = AssessmentService(db)
    return service.create_assessment(data)


@router.put("/{assessment_id}", response_model=AssessmentResponse)
def update_assessment(
    assessment_id: int,
    data: AssessmentUpdateRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """更新评估"""
    service = AssessmentService(db)
    return service.update_assessment(assessment_id, data)


@router.delete("/{assessment_id}")
def delete_assessment(
    assessment_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """删除评估"""
    service = AssessmentService(db)
    return service.delete_assessment(assessment_id)
