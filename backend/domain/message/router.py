# backend/domain/message/router.py
"""消息域 API 路由"""

from fastapi import APIRouter, Depends, Query

from backend.common.dependencies import get_message_service
from backend.middleware.auth import get_current_user
from backend.domain.message.schemas import MessageListResponse
from backend.domain.message.service import MessageService

router = APIRouter(prefix="/message", tags=["消息"])


@router.get("/", response_model=MessageListResponse)
def get_messages(
    msg_type: int | None = Query(None, description="消息类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: MessageService = Depends(get_message_service),
    current_user=Depends(get_current_user),
):
    """获取当前用户消息列表"""
    return service.get_user_messages(current_user.id, msg_type, page, page_size)


@router.put("/{message_id}/read")
def mark_read(
    message_id: int,
    service: MessageService = Depends(get_message_service),
    current_user=Depends(get_current_user),
):
    """标记单条消息已读"""
    ok = service.mark_as_read(message_id, current_user.id)
    return {"success": ok}


@router.put("/read-all")
def mark_all_read(
    service: MessageService = Depends(get_message_service),
    current_user=Depends(get_current_user),
):
    """标记所有消息已读"""
    count = service.mark_all_read(current_user.id)
    return {"success": True, "count": count}
