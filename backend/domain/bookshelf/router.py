# backend/domain/bookshelf/router.py
"""书架域 API 路由 — 想读清单 + 收藏夹"""

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_bookshelf_service
from backend.middleware.ownership import GetOwnedChildFromQuery
from backend.middleware.auth import get_current_user
from backend.domain.bookshelf.schemas import (
    BookshelfAddRequest,
    BookshelfResponse,
    FavoriteAddRequest,
    FavoriteResponse,
)
from backend.domain.bookshelf.service import BookshelfService

router = APIRouter(prefix="/bookshelf", tags=["书架"])
fav_router = APIRouter(prefix="/favorites", tags=["收藏夹"])


# ============================================================
# 想读清单
# ============================================================


@router.post("/", response_model=BookshelfResponse, status_code=201)
def add_to_shelf(
    req: BookshelfAddRequest,
    child_id: int | None = None,
    service: BookshelfService = Depends(get_bookshelf_service),
    current_user=Depends(get_current_user),
):
    """加入想读清单"""
    # FIX: current_child_id 为 NULL 时 cid=None 直接传入会导致 MySQL IntegrityError (1048, Column 'child_id' cannot be null)
    cid = child_id or getattr(current_user, "current_child_id", None)
    if not cid:
        from backend.common.exceptions import ValidationError

        raise ValidationError("请先选择孩子")
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


# ============================================================
# 收藏夹
# ============================================================


@fav_router.post("/", response_model=FavoriteResponse, status_code=201)
def add_favorite(
    req: FavoriteAddRequest,
    child_id: int | None = None,
    service: BookshelfService = Depends(get_bookshelf_service),
    current_user=Depends(get_current_user),
):
    """收藏图书"""
    # 优先使用 query 参数 child_id，其次 current_child_id
    cid = child_id or getattr(current_user, "current_child_id", None)
    if not cid:
        from backend.common.exceptions import ValidationError

        raise ValidationError("请先选择孩子")
    return service.add_favorite(cid, req.book_id)


@fav_router.get("/", response_model=list[FavoriteResponse])
def get_favorites(
    child=Depends(GetOwnedChildFromQuery()),
    service: BookshelfService = Depends(get_bookshelf_service),
):
    """获取收藏夹"""
    # low-volume: per child, typically <=50 favorite books
    return service.get_favorites(child.id)


@fav_router.delete("/{book_id}")
def remove_favorite(
    book_id: int,
    child=Depends(GetOwnedChildFromQuery()),
    service: BookshelfService = Depends(get_bookshelf_service),
):
    """移除收藏"""
    return service.remove_favorite(child.id, book_id)
