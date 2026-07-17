# backend/domain/audio/router.py
"""音频域 API 路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import get_db
from backend.middleware.admin_rbac import require_perm
from backend.domain.audio.schemas import (
    AudioCreateRequest,
    AudioUpdateRequest,
    AudioResponse,
    AudioListResponse,
)
from backend.domain.audio.service import AudioService

router = APIRouter(prefix="/admin/api/audio", tags=["音频管理"])


@router.get("/list", response_model=AudioListResponse)
def list_audios(
    keyword: str | None = None,
    reader: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("content.list")),
    db: Session = Depends(get_db),
):
    """获取音频列表"""
    service = AudioService(db)
    return service.list_audios(keyword, reader, page, page_size)


@router.get("/{audio_id}", response_model=AudioResponse)
def get_audio(
    audio_id: int,
    admin=Depends(require_perm("content.list")),
    db: Session = Depends(get_db),
):
    """获取音频详情"""
    service = AudioService(db)
    return service.get_audio(audio_id)


@router.post("/", response_model=AudioResponse, status_code=201)
def create_audio(
    data: AudioCreateRequest,
    admin=Depends(require_perm("content.create")),
    db: Session = Depends(get_db),
):
    """创建音频"""
    service = AudioService(db)
    return service.create_audio(data)


@router.put("/{audio_id}", response_model=AudioResponse)
def update_audio(
    audio_id: int,
    data: AudioUpdateRequest,
    admin=Depends(require_perm("content.edit")),
    db: Session = Depends(get_db),
):
    """更新音频"""
    service = AudioService(db)
    return service.update_audio(audio_id, data)


@router.delete("/{audio_id}")
def delete_audio(
    audio_id: int,
    admin=Depends(require_perm("content.delete")),
    db: Session = Depends(get_db),
):
    """删除音频"""
    service = AudioService(db)
    return service.delete_audio(audio_id)
