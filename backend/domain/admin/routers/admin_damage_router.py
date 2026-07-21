"""T3.6a 图书损坏定责 — 管理端 API 路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.domain.admin.admin_schemas import AdminActionResponse
from backend.domain.admin.services.damage_admin_service import DamageAdminService
from backend.domain.book.damage_schemas import (
    DamageCreateRequest,
    DamageAppealRequest,
    DamageReviewRequest,
    DamageReportResponse,
)
from backend.middleware.admin_rbac import require_perm

router = APIRouter(prefix="/admin/api/damage-reports", tags=["图书损坏定责"])


@router.post("", response_model=AdminActionResponse)
def create_damage_report(
    req: DamageCreateRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_perm("book_damage.create")),
):
    """登记损坏定级"""
    svc = DamageAdminService(db)
    report = svc.create_report(
        borrow_record_id=req.borrow_record_id,
        damage_level=req.damage_level,
        photo_url=req.photo_url,
        description=req.description,
        admin_id=admin.id,
    )
    from backend.domain.book.damage_schemas import DamageReportResponse as Resp

    return {"success": True, "data": Resp.model_validate(report)}


@router.get("", response_model=AdminActionResponse)
def list_damage_reports(
    status: int | None = Query(None, description="筛选状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(require_perm("book_damage.list")),
):
    """损坏报告列表"""
    svc = DamageAdminService(db)
    return svc.get_list(status=status, page=page, page_size=page_size)


@router.post("/{report_id}/appeal", response_model=AdminActionResponse)
def appeal_damage_report(
    report_id: int,
    req: DamageAppealRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_perm("book_damage.appeal")),
):
    """家长申诉"""
    svc = DamageAdminService(db)
    report = svc.appeal(report_id, req.appeal_reason)
    return {"success": True, "data": DamageReportResponse.model_validate(report)}


@router.post("/{report_id}/review", response_model=AdminActionResponse)
def review_damage_report(
    report_id: int,
    req: DamageReviewRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_perm("book_damage.review")),
):
    """审核申诉 — approve（确认）/ override（冲正改判）"""
    svc = DamageAdminService(db)
    report = svc.review(
        report_id,
        action=req.action,
        override_level=req.override_level,
        override_fine=req.override_fine,
        review_remark=req.review_remark,
        admin_id=admin.id,
    )
    return {"success": True, "data": DamageReportResponse.model_validate(report)}
