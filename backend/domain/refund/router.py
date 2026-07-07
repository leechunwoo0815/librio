# backend/domain/refund/router.py
"""退款域 API 路由"""

from fastapi import APIRouter, BackgroundTasks, Depends

from backend.common.dependencies import get_refund_service
from backend.middleware.admin_auth import require_role, ROLE_ADMIN, ROLE_STAFF
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import GetOwnedRefund
from backend.domain.refund.schemas import RefundCreate, RefundAudit, RefundResponse
from backend.domain.refund.service import RefundService

router = APIRouter(prefix="/refund", tags=["退款"])


@router.post("/", response_model=RefundResponse, status_code=201)
def apply_refund(
    data: RefundCreate,
    service: RefundService = Depends(get_refund_service),
    current_user=Depends(get_current_user),
):
    return service.apply_refund(current_user.id, data)


@router.get("/", response_model=list[RefundResponse])
def get_my_refunds(
    service: RefundService = Depends(get_refund_service),
    current_user=Depends(get_current_user),
):
    return service.get_user_refunds(current_user.id)


@router.get("/{refund_id}", response_model=RefundResponse)
def get_refund_detail(
    refund_id: int,
    _ctx: tuple = Depends(GetOwnedRefund()),
):
    _, refund = _ctx
    return refund


@router.put("/{refund_id}/audit", response_model=RefundResponse)
def audit_refund(
    refund_id: int,
    audit: RefundAudit,
    background_tasks: BackgroundTasks,
    service: RefundService = Depends(get_refund_service),
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
):
    audit.admin_id = admin.id
    result = service.audit_refund(refund_id, audit)

    # 审核通过后，异步执行微信退款
    if audit.status == 1:  # APPROVED
        from backend.domain.refund.models import RefundApplication
        from backend.domain.order.models import Order
        from backend.database import get_session
        db = get_session()()
        try:
            refund = db.query(RefundApplication).filter(RefundApplication.id == refund_id).first()
            if refund:
                order = db.query(Order).filter(Order.id == refund.order_id).first()
                if order:
                    background_tasks.add_task(service._execute_wechat_refund_async, refund, order)
        finally:
            db.close()

    return result
