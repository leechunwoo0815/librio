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
from backend.middleware.admin_rbac import require_perm
from backend.middleware.rate_limit import rate_limit
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    CreateBookRequest,
    UpdateBookRequest,
    BulkImportBookItem,
    CreateBookCopyRequest,
    SaveBookPageRequest,
)
from backend.domain.admin.services.book_service import AdminBookService
from backend.domain.admin.services.export_service import AdminExportService
from backend.domain.admin.services.upload_service import AdminUploadService
from backend.domain.book.service import BookService
from backend.domain.book.schemas import BookSearch, BookCreate

router = APIRouter(prefix="/admin/api", tags=["图书管理"])


# ==================== 图书管理 ====================

@router.get("/books", response_model=AdminActionResponse)
def list_books(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("book.list")),
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
    admin=Depends(require_perm("book.create")),
    db: Session = Depends(get_db),
):
    """创建图书"""
    service = BookService(db)
    book_data = BookCreate(**data.model_dump())
    result = service.create_book(book_data)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="book",
        operation="create",
        content=f"创建图书: {data.title}",
    )
    return result


@router.put("/books/{book_id}", response_model=SuccessResponse)
def update_book(
    book_id: int,
    data: UpdateBookRequest,
    admin=Depends(require_perm("book.edit")),
    db: Session = Depends(get_db),
):
    """更新图书"""
    service = BookService(db)
    result = service.update_book(book_id, data)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="book",
        operation="update",
        content=f"更新图书 #{book_id}",
    )
    return result


@router.delete("/books/{book_id}", response_model=SuccessResponse)
def delete_book(
    book_id: int,
    admin=Depends(require_perm("book.delete")),
    db: Session = Depends(get_db),
):
    """删除图书"""
    service = BookService(db)
    result = service.delete_book(book_id)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="book",
        operation="delete",
        content=f"删除图书 #{book_id}",
    )
    return result


@router.put("/books/{book_id}/toggle-publish", response_model=AdminActionResponse)
def toggle_publish(
    book_id: int,
    admin=Depends(require_perm("book.edit")),
    db: Session = Depends(get_db),
):
    """切换图书发布状态"""
    service = BookService(db)
    result = service.toggle_publish(book_id)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="book",
        operation="toggle_publish",
        content=f"切换图书 #{book_id} 发布状态",
    )
    return result


@router.post("/books/bulk-import", response_model=AdminActionResponse, dependencies=[Depends(rate_limit(5, 60))])
def bulk_import_books(
    books: list[BulkImportBookItem],
    service: AdminBookService = Depends(get_admin_book_service),
    admin=Depends(require_perm("book.import")),
):
    """批量导入图书"""
    result = service.bulk_import_books(books)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="book",
        operation="bulk_import",
        content="批量导入图书: 结果见返回",
    )
    return result


# ==================== 图书副本 ====================

@router.get("/bookcopy", response_model=list)
def list_bookcopies(
    service: AdminBookService = Depends(get_admin_book_service),
    admin=Depends(require_perm("bookcopy.list")),
):
    """获取所有副本列表"""
    return service.list_bookcopies()


@router.post("/bookcopy/batch-generate", response_model=AdminActionResponse)
def batch_generate_copies(
    isbn: str = Query(..., description="图书ISBN"),
    count: int = Query(..., ge=1, le=100, description="生成数量"),
    service: AdminBookService = Depends(get_admin_book_service),
    admin=Depends(require_perm("bookcopy.create")),
):
    """批量生成实体书副本条码"""
    result = service.batch_generate_copies(isbn, count)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="bookcopy",
        operation="batch_generate",
        content="批量生成副本",
    )
    return result


@router.post("/bookcopy/{book_id}/copies", response_model=AdminActionResponse, status_code=201)
def create_book_copy(
    book_id: int,
    data: CreateBookCopyRequest = CreateBookCopyRequest(),
    admin=Depends(require_perm("bookcopy.create")),
    db: Session = Depends(get_db),
):
    """为图书创建副本（支持手动传入条码）"""
    service = BookService(db)
    result = service.create_book_copy_admin(
        book_id,
        barcode=data.barcode,
        location=data.location,
        condition_note=data.condition_note,
    )
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="bookcopy",
        operation="create",
        content=f"为图书 #{book_id} 创建副本",
    )
    return result


# ==================== 图书页面内容 ====================

@router.get("/books/{book_id}/pages", response_model=AdminActionResponse)
def list_book_pages(
    book_id: int,
    admin=Depends(require_perm("book.edit")),
    db: Session = Depends(get_db),
):
    """获取图书页面列表"""
    service = BookService(db)
    return {"items": service.get_book_pages_admin(book_id)}


@router.put("/books/{book_id}/pages/{page_number}", response_model=AdminActionResponse)
def save_book_page(
    book_id: int,
    page_number: int,
    data: SaveBookPageRequest,
    admin=Depends(require_perm("book.edit")),
    db: Session = Depends(get_db),
):
    """保存或更新图书页面内容"""
    service = BookService(db)
    result = service.save_book_page_admin(
        book_id,
        page_number,
        text_content=data.text_content,
        image_url=data.image_url,
        audio_url=data.audio_url,
    )
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="book_page",
        operation="save",
        content=f"保存图书 #{book_id} 第 {page_number} 页",
    )
    return result


# ==================== 文件上传 ====================

UPLOAD_DIR = (Path(__file__).parent.parent.parent.parent.parent / "uploads").resolve()


@router.post("/upload", response_model=AdminActionResponse)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    filename: str = Query(None),
    file_type: str = Query(None),
    service: AdminUploadService = Depends(get_admin_upload_service),
    admin=Depends(require_perm("upload.manage")),
):
    """单文件上传"""
    fname = filename or file.filename or "unknown"
    content = await file.read()
    service.validate_file_extension(fname, file_type)
    result = service.save_upload(fname, content)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="upload",
        operation="upload",
        content="上传文件",
    )
    return result


@router.post("/upload/chunk", response_model=AdminActionResponse)
async def upload_chunk(
    file: UploadFile = FastAPIFile(...),
    upload_id: str = Query(...),
    chunk_index: int = Query(..., ge=0),
    total_chunks: int = Query(..., ge=1),
    filename: str = Query(...),
    file_type: str = Query(None),
    service: AdminUploadService = Depends(get_admin_upload_service),
    admin=Depends(require_perm("upload.manage")),
):
    """分片上传"""
    content = await file.read()
    service.validate_file_extension(filename, file_type)
    result = service.save_chunk(upload_id, chunk_index, total_chunks, filename, content)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="upload",
        operation="chunk_upload",
        content="分片上传",
    )
    return result


@router.post("/upload/complete", response_model=AdminActionResponse)
def complete_upload(
    upload_id: str = Query(...),
    service: AdminUploadService = Depends(get_admin_upload_service),
    admin=Depends(require_perm("upload.manage")),
):
    """合并分片，完成上传"""
    result = service.complete_upload(upload_id)
    from backend.domain.admin.services.system_service import AdminSystemService
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="upload",
        operation="complete_upload",
        content="完成分片上传",
    )
    return result


@router.get("/upload/status/{upload_id}", response_model=AdminActionResponse)
def upload_status(
    upload_id: str,
    service: AdminUploadService = Depends(get_admin_upload_service),
    admin=Depends(require_perm("upload.manage")),
):
    """查询分片上传进度"""
    return service.get_upload_status(upload_id)


# ==================== 批量导出 ====================

@router.get("/export/{module}", response_model=None, dependencies=[Depends(rate_limit(10, 60))])
def export_data(
    module: str,
    service: AdminExportService = Depends(get_admin_export_service),
    admin=Depends(require_perm("book.export")),
):
    """导出数据为 CSV"""
    csv_content, filename = service.export_data(module)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
