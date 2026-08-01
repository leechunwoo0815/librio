"""T3.6a 图书损坏定责 — Pydantic schemas"""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class DamageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    borrow_record_id: int = Field(..., description="借阅记录ID")
    damage_level: int = Field(..., ge=1, le=3, description="定级: 1=轻度 2=重度 3=丢失")
    photo_url: str | None = Field(None, max_length=500, description="损坏照片URL")
    description: str | None = Field(None, description="定责说明")

    @model_validator(mode="after")
    def _require_photo_for_heavy_lost(self):
        if self.damage_level >= 2 and not self.photo_url:
            raise ValueError("重度/丢失定级必须上传损坏照片")
        return self


class DamageAppealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appeal_reason: str = Field(..., min_length=1, description="申诉理由")


class DamageReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(
        ...,
        pattern="^(approve|override)$",
        description="操作: approve=确认罚款 override=冲正改判",
    )
    override_level: int | None = Field(None, ge=1, le=3, description="冲正后定级")
    override_fine: Decimal | None = Field(None, ge=0, description="冲正后罚款金额")
    review_remark: str | None = Field("", description="审核备注")


class DamageRejectRequest(BaseModel):
    """B9：复核驳回"""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field("", max_length=255, description="驳回原因")


class BookFoundRequest(BaseModel):
    """B10：丢失图书找回"""

    model_config = ConfigDict(extra="forbid")

    borrow_record_id: int = Field(..., description="借阅记录ID")


class ReplaceNewCopyRequest(BaseModel):
    """B10：买同 ISBN 新书归还替代赔偿"""

    model_config = ConfigDict(extra="forbid")

    borrow_record_id: int = Field(..., description="借阅记录ID")
    barcode: str = Field(..., min_length=1, max_length=50, description="新副本条码")


class CheckoutPhotosRequest(BaseModel):
    """B9：借出拍照存档（封面/封底/书脊）"""

    model_config = ConfigDict(extra="forbid")

    photos: list[str] = Field(..., min_length=1, max_length=6, description="照片URL列表")


class DamageReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    borrow_record_id: int
    book_copy_id: int | None
    child_id: int
    damage_level: int
    photo_url: str | None
    description: str | None
    fine_amount: Decimal | None
    status: int
    admin_id: int | None
    appeal_reason: str | None
    appeal_result: str | None
    override_level: int | None
    override_fine: Decimal | None
    create_time: datetime | None
