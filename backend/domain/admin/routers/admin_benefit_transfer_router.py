from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.domain.admin.admin_schemas import AdminActionResponse
from backend.domain.admin.services.benefit_transfer_service import BenefitTransferAdminService
from backend.middleware.admin_rbac import require_perm

router = APIRouter(prefix="/admin/api/benefit-transfers", tags=["权益转让审核"])


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_remark: str = Field(default="", description="审核备注")


@router.get("", response_model=AdminActionResponse)
def list_transfers(
    status: int | None = Query(None, description="筛选状态: 0=PENDING 1=APPROVED 2=REJECTED"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(require_perm("benefit_transfer.list")),
):
    svc = BenefitTransferAdminService(db)
    return svc.get_list(status=status, page=page, page_size=page_size)


@router.post("/{application_id}/approve", response_model=AdminActionResponse)
def approve_transfer(
    application_id: int,
    req: ReviewRequest = None,
    db: Session = Depends(get_db),
    admin=Depends(require_perm("benefit_transfer.review")),
):
    svc = BenefitTransferAdminService(db)
    result = svc.approve(application_id, admin.id, req.review_remark if req else "")
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(svc.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="benefit_transfer",
        operation="approve",
        content=f"审核通过权益转让 #{application_id}",
    )
    return result


@router.post("/{application_id}/reject", response_model=AdminActionResponse)
def reject_transfer(
    application_id: int,
    req: ReviewRequest = None,
    db: Session = Depends(get_db),
    admin=Depends(require_perm("benefit_transfer.review")),
):
    svc = BenefitTransferAdminService(db)
    result = svc.reject(application_id, admin.id, req.review_remark if req else "")
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(svc.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="benefit_transfer",
        operation="reject",
        content=f"驳回权益转让 #{application_id}",
    )
    return result
