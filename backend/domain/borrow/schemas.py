# backend/domain/borrow/schemas.py
"""借阅域 Pydantic 模型 — V3.1 OMO"""

from datetime import datetime
from decimal import Decimal


from backend.common.base_schema import BaseSchema, PaginatedResponse


class BorrowBookRequest(BaseSchema):
    """借书请求"""

    child_id: int
    book_id: int
    book_copy_id: int | None = None
    operator_id: int | None = None


class ScanAndBorrowRequest(BaseSchema):
    """扫码借书请求（支持首次扫码自动创建图书+副本）"""

    child_id: int
    barcode: str
    operator_id: int | None = None
    # 以下字段仅在条码不存在时需要（首次扫码创建新书）
    title: str | None = None
    isbn: str | None = None
    ar_value: float | None = None
    age_min: int | None = None
    age_max: int | None = None
    word_count: int | None = None


class ReturnBookRequest(BaseSchema):
    """还书请求"""

    borrow_record_id: int


class ScanAndReturnRequest(BaseSchema):
    """扫码还书请求"""

    barcode: str


class BorrowRecordResponse(BaseSchema):
    """借阅记录响应"""

    id: int
    child_id: int
    book_id: int
    book_copy_id: int | None = None
    borrow_time: datetime
    due_date: datetime
    return_time: datetime | None = None
    status: int
    overdue_days: int = 0
    fine_amount: Decimal = 0
    quiz_passed: int = 0


BorrowListResponse = PaginatedResponse[BorrowRecordResponse]
