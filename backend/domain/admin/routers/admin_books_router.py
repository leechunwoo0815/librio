# backend/domain/admin/routers/admin_books_router.py
"""图书管理路由"""

from pathlib import Path
from fastapi import APIRouter, Depends, Query, UploadFile, File as FastAPIFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.common.dependencies import (
    get_db,
    get_admin_book_service,
    get_admin_upload_service,
    get_admin_export_service,
)
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN, ROLE_STAFF
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    CreateBookRequest,
    UpdateBookRequest,
    BulkImportBookItem,
)
from backend.domain.admin.services.book_service import AdminBookService
from backend.domain.admin.services.export_service import AdminExportService
from backend.domain.admin.services.upload_service import AdminUploadService
from backend.domain.book.service import BookService
from backend.domain.book.schemas import BookSearch, BookCreate

router = APIRouter(prefix="/admin/api", tags=["图书管理"])


# ==================== 图书管理 ====================

@router.get("/books")
def list_books(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
    admin_book_service: AdminBookService = Depends(get_admin_book_service),
):
    """搜索图书 — 返回分页列表 + 全局统计"""
    service = BookService(db)
    search = BookSearch(keyword=keyword, page=page, page_size=page_size)
    result = service.search_books(search)
    stats = admin_book_service.get_book_stats()

    # 返回字典格式，避免 Pydantic 序列化问题
    return {
        "items": [item.model_dump() for item in result.items],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
        "stats": stats,
    }


@router.post("/books", response_model=AdminActionResponse, status_code=201)
def create_book(
    data: CreateBookRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """创建图书"""
    service = BookService(db)
    book_data = BookCreate(**data.model_dump())
    return service.create_book(book_data)


@router.put("/books/{book_id}", response_model=SuccessResponse)
def update_book(
    book_id: int,
    data: UpdateBookRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """更新图书"""
    service = BookService(db)
    return service.update_book(book_id, data)


@router.delete("/books/{book_id}", response_model=SuccessResponse)
def delete_book(
    book_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """删除图书"""
    service = BookService(db)
    return service.delete_book(book_id)


@router.put("/books/{book_id}/toggle-publish", response_model=AdminActionResponse)
def toggle_publish(
    book_id: int,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """切换图书发布状态"""
    service = BookService(db)
    return service.toggle_publish(book_id)


@router.post("/books/bulk-import", response_model=AdminActionResponse)
def bulk_import_books(
    books: list[BulkImportBookItem],
    service: AdminBookService = Depends(get_admin_book_service),
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
):
    """批量导入图书"""
    return service.bulk_import_books(books)


# ==================== 图书副本 ====================

@router.get("/bookcopy", response_model=list)
def list_bookcopies(
    service: AdminBookService = Depends(get_admin_book_service),
    admin=Depends(get_current_admin),
):
    """获取所有副本列表"""
    return service.list_bookcopies()


@router.post("/bookcopy/batch-generate", response_model=AdminActionResponse)
def batch_generate_copies(
    isbn: str = Query(..., description="图书ISBN"),
    count: int = Query(..., ge=1, le=100, description="生成数量"),
    service: AdminBookService = Depends(get_admin_book_service),
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
):
    """批量生成实体书副本条码"""
    return service.batch_generate_copies(isbn, count)


@router.post("/bookcopy/{book_id}/copies", response_model=AdminActionResponse, status_code=201)
def create_book_copy(
    book_id: int,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """为图书创建副本"""
    service = BookService(db)
    return service.create_book_copy_admin(book_id)


# ==================== 文件上传 ====================

UPLOAD_DIR = (Path(__file__).parent.parent.parent.parent.parent / "uploads").resolve()


@router.post("/upload", response_model=AdminActionResponse)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    filename: str = Query(None),
    file_type: str = Query(None),
    service: AdminUploadService = Depends(get_admin_upload_service),
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
):
    """单文件上传"""
    fname = filename or file.filename or "unknown"
    content = await file.read()
    service.validate_file_extension(fname, file_type)
    return service.save_upload(fname, content)


@router.post("/upload/chunk", response_model=AdminActionResponse)
async def upload_chunk(
    file: UploadFile = FastAPIFile(...),
    upload_id: str = Query(...),
    chunk_index: int = Query(..., ge=0),
    total_chunks: int = Query(..., ge=1),
    filename: str = Query(...),
    file_type: str = Query(None),
    service: AdminUploadService = Depends(get_admin_upload_service),
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
):
    """分片上传"""
    content = await file.read()
    service.validate_file_extension(filename, file_type)
    return service.save_chunk(upload_id, chunk_index, total_chunks, filename, content)


@router.post("/upload/complete", response_model=AdminActionResponse)
def complete_upload(
    upload_id: str = Query(...),
    service: AdminUploadService = Depends(get_admin_upload_service),
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
):
    """合并分片，完成上传"""
    return service.complete_upload(upload_id)


@router.get("/upload/status/{upload_id}", response_model=AdminActionResponse)
def upload_status(
    upload_id: str,
    service: AdminUploadService = Depends(get_admin_upload_service),
    admin=Depends(get_current_admin),
):
    """查询分片上传进度"""
    return service.get_upload_status(upload_id)


# ==================== 批量导出 ====================

@router.get("/export/{module}", response_model=None)
def export_data(
    module: str,
    service: AdminExportService = Depends(get_admin_export_service),
    admin=Depends(get_current_admin),
):
    """导出数据为 CSV"""
    csv_content, filename = service.export_data(module)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
