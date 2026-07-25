# backend/domain/venue/router.py
"""场馆公开信息 API — 用户端场馆列表（门店位置为公开信息，无需认证）"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.domain.admin.models import Venue

router = APIRouter(prefix="/venue", tags=["场馆"])


@router.get("/list", response_model=list[dict])
def list_public_venues(db: Session = Depends(get_db)):
    """公开场馆列表（名称/地址/电话/营业时间，仅 active 状态）"""
    venues = (
        db.query(Venue)
        .filter(Venue.is_deleted == 0, Venue.status == "active")
        .order_by(Venue.id)
        .all()
    )
    return [
        {
            "id": v.id,
            "name": v.name,
            "address": v.address,
            "phone": v.phone,
            "business_hours": v.business_hours,
        }
        for v in venues
    ]
