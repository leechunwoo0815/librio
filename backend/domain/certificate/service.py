# backend/domain/certificate/service.py
"""证书域业务逻辑 — 晋级证书生成"""

import logging
from sqlalchemy.orm import Session
from backend.common.base_repo import BaseRepository
from backend.common.exceptions import NotFoundError
from backend.domain.certificate.models import LevelCertificate
from backend.domain.certificate.repository import CertificateRepository

logger = logging.getLogger(__name__)


class CertificateService:
    def __init__(self, db: Session):
        self.db = db
        self.cert_repo = CertificateRepository(db)

    def get_child_certificates(self, child_id: int) -> list[dict]:
        certs = self.cert_repo.get_by_child(child_id)
        return [
            {
                "id": c.id,
                "child_id": c.child_id,
                "level_id": c.level_id,
                "level_name": c.level_name,
                "child_name": c.child_name,
                "child_english_name": c.child_english_name,
                "badge_emoji": c.badge_emoji,
                "certificate_no": c.certificate_no,
                "created_at": c.create_time.isoformat() if c.create_time else None,
            }
            for c in certs
        ]

    def generate_certificate(self, child_id: int, level_id: int) -> dict:
        """生成晋级证书（幂等，已有则返回）"""
        existing = self.cert_repo.get_by_child_and_level(child_id, level_id)
        if existing:
            return {
                "id": existing.id,
                "child_name": existing.child_name,
                "child_english_name": existing.child_english_name,
                "level_name": existing.level_name,
                "badge_emoji": existing.badge_emoji,
                "certificate_no": existing.certificate_no,
                "already_granted": True,
            }

        from backend.domain.child.models import Child
        from backend.domain.advancement.models import Level
        import uuid
        from datetime import datetime

        child = BaseRepository(self.db, Child).get_by_id(child_id)
        level = BaseRepository(self.db, Level).get_by_id(level_id)
        if not child or not level:
            raise NotFoundError("孩子或级别不存在")

        cert_no = (
            f"MW-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        )
        cert = LevelCertificate(
            child_id=child_id,
            level_id=level_id,
            level_name=level.name,
            child_name=child.name,
            child_english_name=child.english_name,
            badge_emoji=level.badge_emoji,
            certificate_no=cert_no,
        )
        created = self.cert_repo.create(cert)
        self.db.commit()
        logger.info(f"Certificate generated: child={child_id}, level={level.name}")
        return {
            "id": created.id,
            "child_name": child.name,
            "child_english_name": child.english_name,
            "level_name": level.name,
            "badge_emoji": level.badge_emoji,
            "certificate_no": cert_no,
            "already_granted": False,
        }

    def get_certificate(self, cert_id: int) -> dict | None:
        """获取单个证书详情"""
        cert = self.cert_repo.get_by_id(cert_id)
        if not cert:
            return None
        return {
            "id": cert.id,
            "child_id": cert.child_id,
            "level_id": cert.level_id,
            "level_name": cert.level_name,
            "child_name": cert.child_name,
            "child_english_name": cert.child_english_name,
            "badge_emoji": cert.badge_emoji,
            "certificate_no": cert.certificate_no,
            "created_at": cert.create_time.isoformat() if cert.create_time else None,
        }

    def create_level_certificate(self, child_id: int, level_name: str) -> dict | None:
        """事件处理器调用：根据级别名称生成证书"""
        from backend.domain.advancement.models import Level

        levels = (
            self.db.query(Level)
            .filter(Level.is_deleted == 0)
            .order_by(Level.sort_order)
            .all()
        )
        for lvl in levels:
            if lvl.name == level_name:
                return self.generate_certificate(child_id, lvl.id)
        return None

    def render_certificate_html(self, cert_id: int) -> str | None:
        cert = self.cert_repo.get_by_id(cert_id)
        if not cert:
            return None
        return f"<html><body><h1>晋级证书</h1><p>{cert.child_name} - {cert.level_name}</p></body></html>"
