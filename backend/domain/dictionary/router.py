# backend/domain/dictionary/router.py
"""词库域 API 路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import get_db
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN, ROLE_STAFF
from backend.domain.dictionary.schemas import (
    WordCreateRequest,
    WordUpdateRequest,
    WordResponse,
    WordListResponse,
)
from backend.domain.dictionary.service import DictionaryService

router = APIRouter(prefix="/admin/api/dictionary", tags=["词库管理"])


@router.get("/search", response_model=WordListResponse)
def search_words(
    keyword: str | None = None,
    level: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """搜索单词"""
    service = DictionaryService(db)
    return service.search_words(keyword, level, page, page_size)


@router.get("/{word_id}", response_model=WordResponse)
def get_word(
    word_id: int,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取单词详情"""
    service = DictionaryService(db)
    return service.get_word(word_id)


@router.post("/", response_model=WordResponse, status_code=201)
def create_word(
    data: WordCreateRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """创建单词"""
    service = DictionaryService(db)
    return service.create_word(data)


@router.put("/{word_id}", response_model=WordResponse)
def update_word(
    word_id: int,
    data: WordUpdateRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """更新单词"""
    service = DictionaryService(db)
    return service.update_word(word_id, data)


@router.delete("/{word_id}")
def delete_word(
    word_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """删除单词"""
    service = DictionaryService(db)
    return service.delete_word(word_id)
