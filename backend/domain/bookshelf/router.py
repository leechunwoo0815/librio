# backend/domain/bookshelf/router.py
"""书架域 API 路由 — 想读清单（D5: favorites 收藏夹已并入删除）"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.common.dependencies import get_bookshelf_service
from backend.middleware.ownership import GetOwnedChildFromQuery, verify_child_ownership
from backend.middleware.auth import get_current_user
from backend.database import get_db
from backend.domain.bookshelf.schemas import (
    BookshelfAddRequest,
    BookshelfResponse,
)
from backend.domain.bookshelf.service import BookshelfService

router = APIRouter(prefix="/bookshelf", tags=["书架"])


# ============================================================
# 想读清单
# ============================================================


@router.post("/", response_model=BookshelfResponse, status_code=201)
def add_to_shelf(
    req: BookshelfAddRequest,
    child_id: int | None = None,
    service: BookshelfService = Depends(get_bookshelf_service),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """加入想读清单"""
    # FIX: current_child_id 为 NULL 时 cid=None 直接传入会导致 MySQL IntegrityError (1048, Column 'child_id' cannot be null)
    cid = child_id or getattr(current_user, "current_child_id", None)
    if not cid:
        from backend.common.exceptions import ValidationError

        raise ValidationError("请先选择孩子")
    verify_child_ownership(cid, current_user, db)
    return service.add_to_shelf(cid, req.book_id)


@router.get("/", response_model=list[BookshelfResponse])
def get_shelf(
    child=Depends(GetOwnedChildFromQuery()),
    service: BookshelfService = Depends(get_bookshelf_service),
):
    """获取书架列表"""
    return service.get_shelf(child.id)


@router.put("/{book_id}/finish", response_model=BookshelfResponse)
def mark_as_finished(
    book_id: int,
    child=Depends(GetOwnedChildFromQuery()),
    service: BookshelfService = Depends(get_bookshelf_service),
):
    """标记为已读"""
    return service.mark_as_finished(child.id, book_id)


@router.delete("/{book_id}")
def remove_from_shelf(
    book_id: int,
    child=Depends(GetOwnedChildFromQuery()),
    service: BookshelfService = Depends(get_bookshelf_service),
):
    """从书架移除"""
    return service.remove_from_shelf(child.id, book_id)
