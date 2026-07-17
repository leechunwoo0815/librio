# backend/domain/borrow/router.py
"""借阅域 API 路由 — V3.1 OMO"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_borrow_service
from backend.domain.borrow.schemas import (
    BorrowBookRequest,
    ScanAndBorrowRequest,
    ScanAndReturnRequest,
    ReturnBookRequest,
    BorrowRecordResponse,
)
from backend.domain.borrow.service import BorrowService
from backend.middleware.admin_rbac import require_perm
from backend.middleware.ownership import GetOwnedChild

router = APIRouter(prefix="/borrow", tags=["借阅"])


@router.post("/", response_model=BorrowRecordResponse, status_code=201)
def borrow_book(
    data: BorrowBookRequest,
    service: BorrowService = Depends(get_borrow_service),
    admin=Depends(require_perm("borrow.create")),
):
    """借书"""
    return service.borrow_book(data)


@router.post("/scan", response_model=BorrowRecordResponse, status_code=201)
def scan_and_borrow(
    data: ScanAndBorrowRequest,
    service: BorrowService = Depends(get_borrow_service),
    admin=Depends(require_perm("borrow.create")),
):
    """扫码借书 — 条码存在直接借阅，不存在自动创建图书+副本后借阅"""
    return service.scan_and_borrow(
        child_id=data.child_id,
        barcode=data.barcode,
        operator_id=data.operator_id or admin.id,
        title=data.title,
        isbn=data.isbn,
        ar_value=data.ar_value,
        age_min=data.age_min,
        age_max=data.age_max,
        word_count=data.word_count,
    )


@router.post("/return", response_model=BorrowRecordResponse)
def return_book(
    data: ReturnBookRequest,
    service: BorrowService = Depends(get_borrow_service),
    admin=Depends(require_perm("borrow.return")),
):
    """还书"""
    return service.return_book(data)


@router.post("/scan-return", response_model=BorrowRecordResponse)
def scan_and_return(
    data: ScanAndReturnRequest,
    service: BorrowService = Depends(get_borrow_service),
    admin=Depends(require_perm("borrow.return")),
):
    """扫码还书 — 通过条码找到活跃借阅记录并还书"""
    return service.scan_and_return(data.barcode)


@router.get("/{child_id}", response_model=list[BorrowRecordResponse])
def get_child_borrows(
    status: int | None = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    child=Depends(GetOwnedChild()),
    service: BorrowService = Depends(get_borrow_service),
):
    """获取孩子借阅列表"""
    records, _ = service.get_child_borrows(child.id, status, page, page_size)
    return records
