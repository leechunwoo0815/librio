# backend/domain/reading/router.py
"""阅读域 API 路由"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_reading_service
from backend.middleware.ownership import (
    GetOwnedChild,
    GetOwnedChildFromBody,
    GetOwnedChildFromQuery,
    GetOwnedSession,
)
from backend.middleware.auth import get_current_user
from backend.domain.reading.schemas import (
    BookPageResponse,
    ProgressResponse,
    SaveProgressRequest,
    StartSessionRequest,
    EndSessionRequest,
    SessionResponse,
    CheckInResponse,
    StreakResponse,
    SaveRecordingRequest,
    VoiceRecordingResponse,
    VoiceRecordingDetailResponse,
)
from backend.domain.reading.service import ReadingService

router = APIRouter(prefix="/reading", tags=["阅读"])


@router.get("/pages/{book_id}", response_model=list[BookPageResponse])
def get_book_pages(
    book_id: int,
    service: ReadingService = Depends(get_reading_service),
    current_user=Depends(get_current_user),
):
    """获取图书所有页面"""
    return service.get_book_pages(book_id)


@router.get("/progress/{child_id}/{book_id}", response_model=ProgressResponse | None)
def get_progress(
    book_id: int,
    child=Depends(GetOwnedChild()),
    service: ReadingService = Depends(get_reading_service),
):
    """获取阅读进度"""
    return service.get_progress(child.id, book_id)


@router.post("/progress", response_model=ProgressResponse)
def save_progress(
    data: SaveProgressRequest,
    service: ReadingService = Depends(get_reading_service),
    current_user=Depends(get_current_user),
):
    """保存阅读进度"""
    child_id = getattr(current_user, "current_child_id", None)
    if not child_id:
        from backend.common.exceptions import ValidationError

        raise ValidationError("请先选择孩子")
    return service.save_progress(child_id, data)


@router.post("/session/start", response_model=SessionResponse, status_code=201)
def start_session(
    data: StartSessionRequest,
    service: ReadingService = Depends(get_reading_service),
    current_user=Depends(get_current_user),
):
    """开始阅读会话"""
    child_id = getattr(current_user, "current_child_id", None) or data.child_id
    return service.start_session(child_id, data)


@router.put("/session/{session_id}/end", response_model=SessionResponse)
def end_session(
    data: EndSessionRequest,
    service: ReadingService = Depends(get_reading_service),
    result=Depends(GetOwnedSession()),
):
    """结束阅读会话"""
    _, session = result
    return service.end_session(session.id, data)


@router.get("/checkin/{child_id}", response_model=list[CheckInResponse])
def get_checkin_calendar(
    year: int = Query(...),
    month: int = Query(...),
    child=Depends(GetOwnedChild()),
    service: ReadingService = Depends(get_reading_service),
):
    """获取月度打卡日历"""
    return service.get_checkin_calendar(child.id, year, month)


@router.get("/streak/{child_id}", response_model=StreakResponse)
def get_streak(
    child=Depends(GetOwnedChild()),
    service: ReadingService = Depends(get_reading_service),
):
    """获取连续打卡信息"""
    return service.get_streak(child.id)


# ==================== 语音朗读 ====================


@router.post("/voice/record", response_model=VoiceRecordingResponse, status_code=201)
def save_voice_recording(
    data: SaveRecordingRequest,
    service: ReadingService = Depends(get_reading_service),
    child=Depends(GetOwnedChildFromBody()),
):
    """保存语音录音"""
    return service.save_recording(data)


@router.get("/voice/records", response_model=list[VoiceRecordingDetailResponse])
def get_voice_recordings(
    book_id: int | None = None,
    child=Depends(GetOwnedChildFromQuery()),
    service: ReadingService = Depends(get_reading_service),
):
    """获取语音录音列表"""
    return service.get_recordings(child.id, book_id)
