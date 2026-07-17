# backend/domain/certificate/schemas.py
"""证书域 Pydantic 模型"""

from backend.common.base_schema import BaseSchema


class CertificateResponse(BaseSchema):
    """证书响应模型 — 字段与 service.get_child_certificates 返回的 dict 结构对齐"""

    id: int
    child_id: int
    level_id: int
    level_name: str | None = None
    child_name: str | None = None
    child_english_name: str | None = None
    badge_emoji: str | None = None
    certificate_no: str | None = None
    create_time: str | None = None
