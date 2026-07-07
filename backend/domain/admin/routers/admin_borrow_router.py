# backend/domain/admin/routers/admin_borrow_router.py
"""借阅管理路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import (
    get_db,
    get_admin_message_service,
    get_admin_borrow_service,
)
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN, ROLE_STAFF
from backend.domain.admin.admin_schemas import (
    AdminActionResponse,
    BorrowBookRequest,
    ReturnBookRequest,
    RequestRefundRequest,
    FulfillReservationRequest,
    AdminPayDepositRequest,
    AdminCreateReservationRequest,
)
from backend.domain.admin.services.borrow_service import AdminBorrowService
from backend.domain.admin.services.message_service import AdminMessageService
from backend.domain.borrow.service import BorrowService
from backend.domain.borrow.schemas import (
    BorrowBookRequest as BorrowBookSchema,
    ReturnBookRequest as ReturnBookSchema,
)
from backend.domain.deposit.service import DepositService
from backend.domain.deposit.schemas import DepositRefundRequest
from backend.domain.reservation.service import ReservationService
from backend.domain.reservation.schemas import ReservationFulfillRequest

router = APIRouter(prefix="/admin/api", tags=["借阅管理"])


# ==================== 借阅管理 ====================

@router.get("/borrows", response_model=AdminActionResponse)
def list_borrows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: int | None = None,
    admin=Depends(get_current_admin),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """获取借阅列表 — 带分页"""
    return service.list_borrows(page, page_size, status)


@router.get("/borrows/{child_id}", response_model=list)
def get_child_borrows(
    child_id: int,
    status: int | None = None,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取孩子借阅列表"""
    service = BorrowService(db)
    return service.get_child_borrows(child_id, status)


@router.post("/borrows", response_model=AdminActionResponse, status_code=201)
def borrow_book(
    data: BorrowBookRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """借书"""
    service = BorrowService(db)
    req = BorrowBookSchema(**data.model_dump())
    return service.borrow_book(req)


@router.post("/borrows/return", response_model=AdminActionResponse)
def return_book(
    data: ReturnBookRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """还书"""
    service = BorrowService(db)
    req = ReturnBookSchema(**data.model_dump())
    return service.return_book(req)


@router.post("/borrows/send-overdue-reminders", response_model=AdminActionResponse)
def send_overdue_reminders(
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    service: AdminMessageService = Depends(get_admin_message_service),
):
    """发送逾期提醒"""
    return service.send_overdue_reminders(admin.id)


# ==================== 罚款管理 ====================

@router.post("/children/{child_id}/clear-fines", response_model=AdminActionResponse)
def clear_child_fines(
    child_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """管理员清零孩子罚款"""
    return service.clear_child_fines(child_id, admin.id)


# ==================== 押金管理 ====================

@router.get("/deposits", response_model=AdminActionResponse)
def list_deposits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """获取押金列表 — 带分页"""
    return service.list_deposits(page, page_size)


@router.post("/deposits/refund", response_model=AdminActionResponse)
def request_refund(
    data: RequestRefundRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """申请退款"""
    service = DepositService(db)
    req = DepositRefundRequest(child_id=data.child_id)
    return service.refund_deposit(req)


@router.post("/deposits/pay", response_model=AdminActionResponse)
def admin_pay_deposit(
    data: AdminPayDepositRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """管理员代缴押金"""
    from backend.domain.deposit.schemas import DepositPayRequest

    service = DepositService(db)
    req = DepositPayRequest(child_id=data.child_id)
    result = service.pay_deposit(req)
    return result.model_dump() if hasattr(result, 'model_dump') else result


# ==================== 预约管理 ====================

@router.get("/reservations", response_model=AdminActionResponse)
def list_reservations(
    child_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """获取预约列表 — 带分页"""
    return service.list_reservations(page, page_size)


@router.post("/reservations/fulfill", response_model=AdminActionResponse)
def fulfill_reservation(
    data: FulfillReservationRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """完成预约"""
    service = ReservationService(db)
    req = ReservationFulfillRequest(**data.model_dump())
    return service.fulfill_reservation(req)


@router.put("/reservations/{reservation_id}/cancel", response_model=AdminActionResponse)
def cancel_reservation(
    reservation_id: int,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """取消预约"""
    service = ReservationService(db)
    return service.cancel_reservation(reservation_id)


@router.post("/reservations", response_model=AdminActionResponse, status_code=201)
def admin_create_reservation(
    data: AdminCreateReservationRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """管理员创建预约"""
    from backend.domain.reservation.schemas import ReservationCreateRequest

    service = ReservationService(db)
    req = ReservationCreateRequest(child_id=data.child_id, book_id=data.book_id)
    result = service.create_reservation(req)
    return result.model_dump() if hasattr(result, 'model_dump') else result
