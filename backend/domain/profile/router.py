# backend/domain/profile/router.py
"""名片域 API 路由"""

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_profile_service
from backend.domain.profile.schemas import ProfileResponse
from backend.domain.profile.service import ProfileService
from backend.middleware.ownership import GetOwnedChild

router = APIRouter(prefix="/profile", tags=["名片"])


@router.get("/{child_id}", response_model=ProfileResponse | None)
def get_profile(
    child=Depends(GetOwnedChild()),
    service: ProfileService = Depends(get_profile_service),
):
    return service.get_profile(child.id)
