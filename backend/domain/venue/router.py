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


@router.get("/contact", response_model=dict)
def get_service_contact(db: Session = Depends(get_db)):
    """G2 人工兜底联系方式 — 错误页/提示附门店电话+微信客服入口"""
    from backend.common.config_service import ConfigService

    venue = (
        db.query(Venue)
        .filter(Venue.is_deleted == 0, Venue.status == "active")
        .order_by(Venue.id)
        .first()
    )
    return {
        "venue_name": venue.name if venue else None,
        "phone": venue.phone if venue else None,
        "wechat": ConfigService.get_str(db, "service_wechat", ""),
    }
