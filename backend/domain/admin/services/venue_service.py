# backend/domain/admin/services/venue_service.py
"""场馆管理 Service — 从 AdminService 拆分出来的独立域服务。"""

import logging

from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError
from backend.domain.admin.models import Venue
from backend.domain.admin.repository import VenueRepository
from backend.domain.admin.schemas import (
    CreateVenueRequest,
    UpdateVenueRequest,
    VenueResponse,
)

logger = logging.getLogger(__name__)


class AdminVenueService:
    """场馆管理：负责场馆的 CRUD。"""

    def __init__(self, db: Session):
        self.db = db
        self.venue_repo = VenueRepository(db)

    def list_venues(self, page: int = 1, page_size: int = 100) -> dict:
        offset = (page - 1) * page_size
        items = self.venue_repo.list_all(limit=page_size, offset=offset)
        total = self.venue_repo.count()
        return {
            "items": [VenueResponse.model_validate(v) for v in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
        }

    def create_venue(self, data: CreateVenueRequest) -> VenueResponse:
        """创建场馆"""
        venue = Venue(
            name=data.name,
            address=data.address,
            phone=data.phone,
            business_hours=data.business_hours,
            status=data.status or "active",
            capacity=data.capacity or 0,
        )
        created = self.venue_repo.create(venue)
        self.db.commit()
        return VenueResponse.model_validate(created)

    def delete_venue(self, venue_id: int) -> dict:
        """删除场馆"""
        self.venue_repo.soft_delete(venue_id)
        self.db.commit()
        return {"success": True}

    def update_venue(self, venue_id: int, data: UpdateVenueRequest) -> dict:
        """更新场馆"""
        venue = self.venue_repo.get_by_id(venue_id)
        if not venue or venue.is_deleted == 1:
            raise NotFoundError("场馆不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(venue, key):
                setattr(venue, key, value)
        self.venue_repo.update(venue)
        self.db.commit()
        return {"success": True, "message": "场馆更新成功"}
