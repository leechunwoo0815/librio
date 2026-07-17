# backend/domain/admin/routers/admin_borrow_router.py
"""借阅管理路由"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.common.dependencies import (
    get_db,
    get_payment_gateway,
    get_admin_message_service,
    get_admin_borrow_service,
)
from backend.common.exceptions import ForbiddenError
from backend.common.gateways.payment import PaymentGateway
from backend.middleware.admin_rbac import require_perm
from backend.domain.admin.admin_schemas import (
    AdminActionResponse,
    PaginatedResponse,
    BorrowBookRequest,
    ReturnBookRequest,
    RequestRefundRequest,
    FulfillReservationRequest,
    AdminPayDepositRequest,
    AdminCreateReservationRequest,
)
from backend.domain.activity.service import ActivityService
from backend.domain.admin.services.borrow_service import AdminBorrowService
from backend.domain.admin.services.message_service import AdminMessageService
from backend.domain.admin.services.account_service import AdminAccountService
from backend.domain.borrow.service import BorrowService
from backend.domain.borrow.schemas import (
    BorrowBookRequest as BorrowBookSchema,
    ReturnBookRequest as ReturnBookSchema,
)
from backend.domain.deposit.service import DepositService
from backend.domain.deposit.schemas import (
    DepositPayRequest,
    DepositRefundRequest,
    DepositDeductRequest,
)
from backend.domain.reservation.service import ReservationService
from backend.domain.reservation.schemas import ReservationFulfillRequest

router = APIRouter(prefix="/admin/api", tags=["借阅管理"])


class AuditRefundRequest(BaseModel):
    action: str  # "approve" | "reject"


# ==================== 孩子列表（借还下拉框）====================


@router.get("/children", response_model=list)
def list_children(
    admin=Depends(require_perm("child.list")),
    db: Session = Depends(get_db),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """列出所有可用孩子 — 供扫码借还页面下拉选择"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    return service.list_children(child_ids=child_ids)


# ==================== 借阅管理 ====================


@router.get("/borrows", response_model=AdminActionResponse)
def list_borrows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: int | None = None,
    admin=Depends(require_perm("borrow.list")),
    db: Session = Depends(get_db),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """获取借阅列表 — 带分页"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    return service.list_borrows(page, page_size, status, child_ids=child_ids)


@router.get("/borrows/{child_id}", response_model=PaginatedResponse)
def get_child_borrows(
    child_id: int,
    status: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("borrow.list")),
    db: Session = Depends(get_db),
):
    """获取孩子借阅列表 — 带分页"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    if child_ids is not None and child_id not in child_ids:
        raise ForbiddenError("无权操作该孩子或无访问权限")
    service = BorrowService(db)
    records, total = service.get_child_borrows(child_id, status, page, page_size)
    return PaginatedResponse(
        items=[r.model_dump() for r in records],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size < total),
    )


@router.post("/borrows", response_model=AdminActionResponse, status_code=201)
def borrow_book(
    data: BorrowBookRequest,
    admin=Depends(require_perm("borrow.create")),
    db: Session = Depends(get_db),
):
    """借书"""
    service = BorrowService(db)
    req = BorrowBookSchema(**data.model_dump())
    result = service.borrow_book(req)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="borrow",
        operation="create",
        content=f"借书: {data.model_dump()}",
    )
    return result


@router.post("/borrows/return", response_model=AdminActionResponse)
def return_book(
    data: ReturnBookRequest,
    admin=Depends(require_perm("borrow.return")),
    db: Session = Depends(get_db),
):
    """还书"""
    service = BorrowService(db)
    req = ReturnBookSchema(**data.model_dump())
    result = service.return_book(req)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="borrow",
        operation="return",
        content=f"还书: {data.model_dump()}",
    )
    return result


@router.post("/borrows/send-overdue-reminders", response_model=AdminActionResponse)
def send_overdue_reminders(
    admin=Depends(require_perm("borrow.list")),
    service: AdminMessageService = Depends(get_admin_message_service),
):
    """发送逾期提醒"""
    result = service.send_overdue_reminders(admin.id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="borrow",
        operation="send_overdue_reminders",
        content="发送逾期提醒",
    )
    return result


# ==================== 罚款管理 ====================


@router.post(
    "/borrows/{borrow_record_id}/mark-lost", response_model=AdminActionResponse
)
def mark_borrow_lost(
    borrow_record_id: int,
    admin=Depends(require_perm("borrow.mark_lost")),
    db: Session = Depends(get_db),
):
    """标记图书丢失 — 计算罚款 + 扣减库存"""
    service = DepositService(db)
    result = service.mark_book_lost(borrow_record_id, admin.id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="borrow",
        operation="mark_lost",
        content=f"标记图书丢失: borrow #{borrow_record_id}, fine={result.get('fine_amount', '?')}",
    )
    return result


@router.post("/children/{child_id}/clear-fines", response_model=AdminActionResponse)
def clear_child_fines(
    child_id: int,
    admin=Depends(require_perm("borrow.fine_clear")),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """管理员清零孩子罚款"""
    result = service.clear_child_fines(child_id, admin.id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="borrow",
        operation="clear_fines",
        content=f"清零孩子 #{child_id} 罚款",
    )
    return result


# ==================== 押金管理 ====================


@router.get("/deposits", response_model=AdminActionResponse)
def list_deposits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("deposit.list")),
    db: Session = Depends(get_db),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """获取押金列表 — 带分页"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    return service.list_deposits(page, page_size, child_ids=child_ids)


@router.post("/deposits/{child_id}/audit-refund", response_model=AdminActionResponse)
async def audit_refund(
    child_id: int,
    data: AuditRefundRequest,
    admin=Depends(require_perm("deposit.refund")),
    db: Session = Depends(get_db),
    payment_gateway: PaymentGateway = Depends(get_payment_gateway),
):
    """管理员审核押金退款 — approve 通过/reject 拒绝"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    if child_ids is not None and child_id not in child_ids:
        raise ForbiddenError("无权操作该孩子或无访问权限")
    service = DepositService(db)
    result = await service.audit_refund(
        child_id, data.action, admin.id, payment_gateway
    )
    return result


@router.post("/deposits/refund", response_model=AdminActionResponse)
def request_refund(
    data: RequestRefundRequest,
    admin=Depends(require_perm("deposit.refund")),
    db: Session = Depends(get_db),
):
    """申请退款"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    if child_ids is not None and data.child_id not in child_ids:
        raise ForbiddenError("无权操作该孩子或无访问权限")
    service = DepositService(db)
    req = DepositRefundRequest(child_id=data.child_id)
    result = service.refund_deposit(req)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="deposit",
        operation="refund",
        content=f"申请退款: child #{data.child_id}",
    )
    return result


@router.post("/deposits/pay", response_model=AdminActionResponse)
async def admin_pay_deposit(
    data: AdminPayDepositRequest,
    admin=Depends(require_perm("deposit.pay")),
    db: Session = Depends(get_db),
    payment_gateway: PaymentGateway = Depends(get_payment_gateway),
):
    """管理员代缴押金"""
    service = DepositService(db)
    req = DepositPayRequest(child_id=data.child_id)
    result = await service.pay_deposit(req, payment_gateway)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="deposit",
        operation="pay",
        content=f"代缴押金: child #{data.child_id}",
    )
    return result.model_dump() if hasattr(result, "model_dump") else result


@router.post("/deposits/{child_id}/cancel-refund", response_model=AdminActionResponse)
def admin_cancel_refund(
    child_id: int,
    admin=Depends(require_perm("deposit.refund")),
    db: Session = Depends(get_db),
):
    """取消退款申请"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    if child_ids is not None and child_id not in child_ids:
        raise ForbiddenError("无权操作该孩子或无访问权限")
    service = DepositService(db)
    result = service.cancel_refund(child_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="deposit",
        operation="cancel_refund",
        content=f"取消退款申请: child #{child_id}",
    )
    return result


@router.post("/deposits/{child_id}/mark-refunded", response_model=AdminActionResponse)
def admin_mark_refunded(
    child_id: int,
    admin=Depends(require_perm("deposit.refund")),
    db: Session = Depends(get_db),
):
    """标记押金退款已到账"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    if child_ids is not None and child_id not in child_ids:
        raise ForbiddenError("无权操作该孩子或无访问权限")
    service = DepositService(db)
    result = service.mark_refunded(child_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="deposit",
        operation="mark_refunded",
        content=f"标记退款已到账: child #{child_id}",
    )
    return result


@router.post("/deposits/deduct", response_model=AdminActionResponse)
def admin_deduct_deposit(
    data: DepositDeductRequest,
    admin=Depends(require_perm("deposit.deduct")),
    db: Session = Depends(get_db),
):
    """管理员扣除押金"""
    service = DepositService(db)
    result = service.deduct_deposit(data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="deposit",
        operation="deduct",
        content=f"扣除押金: {data.model_dump()}",
    )
    return result


# ==================== 预约管理 ====================


@router.get("/reservations", response_model=AdminActionResponse)
def list_reservations(
    child_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("reservation.list")),
    db: Session = Depends(get_db),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
):
    """获取预约列表 — 带分页"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    return service.list_reservations(page, page_size, child_ids=child_ids)


@router.post("/reservations/fulfill", response_model=AdminActionResponse)
def fulfill_reservation(
    data: FulfillReservationRequest,
    admin=Depends(require_perm("reservation.fulfill")),
    db: Session = Depends(get_db),
):
    """完成预约"""
    service = ReservationService(db)
    req = ReservationFulfillRequest(reservation_id=data.reservation_id)
    result = service.fulfill_reservation(req)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="reservation",
        operation="fulfill",
        content=f"完成预约: reservation #{data.reservation_id}",
    )
    return result


@router.put("/reservations/{reservation_id}/cancel", response_model=AdminActionResponse)
def cancel_reservation(
    reservation_id: int,
    admin=Depends(require_perm("reservation.cancel")),
    db: Session = Depends(get_db),
):
    """取消预约"""
    service = ReservationService(db)
    result = service.cancel_reservation(reservation_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="reservation",
        operation="cancel",
        content=f"取消预约: reservation #{reservation_id}",
    )
    return result


@router.post("/reservations", response_model=AdminActionResponse, status_code=201)
def admin_create_reservation(
    data: AdminCreateReservationRequest,
    admin=Depends(require_perm("reservation.create")),
    db: Session = Depends(get_db),
):
    """管理员创建预约"""
    from backend.domain.reservation.schemas import ReservationCreateRequest

    service = ReservationService(db)
    req = ReservationCreateRequest(child_id=data.child_id, book_id=data.book_id)
    result = service.create_reservation(req)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="reservation",
        operation="create",
        content=f"创建预约: child #{data.child_id}, book #{data.book_id}",
    )
    return result.model_dump() if hasattr(result, "model_dump") else result


@router.put("/enrollments/{ticket_code}/sign-in", response_model=AdminActionResponse)
def sign_in_by_ticket_code(
    ticket_code: str,
    admin=Depends(require_perm("activity.checkin")),
    db: Session = Depends(get_db),
):
    """通过票码（二维码）签到"""
    service = ActivityService(db)
    result = service.sign_in_by_ticket_code(ticket_code)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="activity",
        operation="ticket_sign_in",
        content=f"票码签到: {ticket_code}",
    )
    return result
