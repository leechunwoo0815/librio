# backend/domain/user/consent_router.py
"""同意记录 API 路由 — 三段式监护人同意"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.domain.user.consent_service import ConsentService
from backend.domain.user.schemas import (
    ConsentCreateRequest,
    ConsentListResponse,
    ConsentResponse,
    ConsentWithdrawRequest,
)

router = APIRouter(prefix="/user/consent", tags=["同意记录"])


def get_consent_service(db: Session = Depends(get_db)) -> ConsentService:
    return ConsentService(db)


@router.post("", response_model=ConsentResponse, status_code=201)
def grant_consent(
    data: ConsentCreateRequest,
    request: Request,
    current_user=Depends(get_current_user),
    service: ConsentService = Depends(get_consent_service),
):
    """用户提交同意（privacy_policy / child_data / voice_recording）"""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:500]
    return service.grant_consent(current_user.id, data.consent_type, ip, ua)


@router.get("", response_model=ConsentListResponse)
def get_consents(
    current_user=Depends(get_current_user),
    service: ConsentService = Depends(get_consent_service),
):
    """获取当前用户所有同意记录"""
    return service.get_consents(current_user.id)


@router.post("/withdraw", response_model=ConsentResponse)
def withdraw_consent(
    data: ConsentWithdrawRequest,
    current_user=Depends(get_current_user),
    service: ConsentService = Depends(get_consent_service),
):
    """撤回同意（privacy_policy / voice_recording）"""
    return service.withdraw_consent(current_user.id, data.consent_type)
