# backend/domain/certificate/router.py
"""证书域 API 路由"""

from fastapi import APIRouter, Depends

from backend.common.dependencies import get_certificate_service
from backend.domain.certificate.schemas import CertificateResponse
from backend.domain.certificate.service import CertificateService
from backend.middleware.ownership import GetOwnedChild

router = APIRouter(prefix="/certificate", tags=["证书"])


@router.get("/{child_id}", response_model=list[CertificateResponse])
def get_certificates(
    child=Depends(GetOwnedChild()),
    service: CertificateService = Depends(get_certificate_service),
):
    return service.get_child_certificates(child.id)
