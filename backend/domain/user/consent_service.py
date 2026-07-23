# backend/domain/user/consent_service.py
"""同意记录业务逻辑 — 三段式监护人同意"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.common.consent_texts import CONSENT_VERSION, get_consent_hash
from backend.common.exceptions import NotFoundError, ValidationError
from backend.domain.user.consent_model import ConsentRecord
from backend.domain.user.consent_repository import ConsentRepository
from backend.domain.user.schemas import ConsentListResponse, ConsentResponse

logger = logging.getLogger(__name__)


class ConsentService:
    """同意记录服务"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ConsentRepository(db)

    def grant_consent(
        self,
        user_id: int,
        consent_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ConsentResponse:
        """用户提交同意"""
        if consent_type not in ConsentRecord.VALID_TYPES:
            raise ValidationError(f"无效的同意类型: {consent_type}")

        text_hash = get_consent_hash(consent_type)

        record = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            consent_text_hash=text_hash,
            consent_version=CONSENT_VERSION,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        created = self.repo.create(record)
        self.db.commit()

        logger.info(
            f"Consent granted: user_id={user_id}, type={consent_type}, "
            f"version={CONSENT_VERSION}, id={created.id}"
        )
        return ConsentResponse.model_validate(created)

    def get_consents(self, user_id: int) -> ConsentListResponse:
        """获取用户所有同意记录（每类最新一条有效记录）"""
        records = self.repo.get_all_for_user(user_id)
        # 每类只返回最新一条
        seen: set[str] = set()
        latest: list[ConsentResponse] = []
        for r in records:
            if r.consent_type not in seen:
                seen.add(r.consent_type)
                latest.append(ConsentResponse.model_validate(r))
        return ConsentListResponse(consents=latest)

    def withdraw_consent(self, user_id: int, consent_type: str) -> ConsentResponse:
        """撤回同意

        child_data 撤回 = 对该用户所有孩子发起级联删除（P0-3）：
        先全量前置校验（任一孩子阻塞则整体拒绝），再标记撤回并逐个发起删除请求。
        """
        if consent_type == "child_data":
            from backend.domain.child.deletion_service import ChildDeletionService
            from backend.domain.child.models import Child

            record = self.repo.get_latest_valid(user_id, consent_type)
            if record is None:
                raise NotFoundError(f"未找到有效的 {consent_type} 同意记录")

            children = (
                self.db.query(Child)
                .filter(Child.user_id == user_id, Child.is_deleted == 0)
                .all()
            )
            svc = ChildDeletionService(self.db)
            all_blockers: list[str] = []
            for c in children:
                all_blockers.extend(svc.check_deletion_blockers(c.id))
            if all_blockers:
                raise ValidationError(
                    "撤回失败，请先处理以下事项：" + "；".join(all_blockers)
                )

            record.withdrawn_at = datetime.now()
            self.repo.update(record)
            self.db.commit()

            for c in children:
                svc.request_deletion(user_id, c.id)

            logger.info(
                f"Consent withdrawn with cascade deletion: user_id={user_id}, "
                f"children={len(children)}"
            )
            return ConsentResponse.model_validate(record)

        record = self.repo.get_latest_valid(user_id, consent_type)
        if record is None:
            raise NotFoundError(f"未找到有效的 {consent_type} 同意记录")

        record.withdrawn_at = datetime.now()
        self.repo.update(record)
        self.db.commit()

        logger.info(
            f"Consent withdrawn: user_id={user_id}, type={consent_type}, id={record.id}"
        )
        return ConsentResponse.model_validate(record)

    def has_valid_consent(self, user_id: int, consent_type: str) -> bool:
        """检查用户是否有有效的同意记录"""
        return self.repo.get_latest_valid(user_id, consent_type) is not None
