# backend/domain/user/repository.py
"""用户域数据访问层 — 继承 BaseRepository，扩展用户特有查询"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.user.models import User


class UserRepository(BaseRepository[User]):
    """用户仓库 — 扩展 openid/phone 查询"""

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_openid(self, openid: str) -> User | None:
        """根据 openid 查询用户"""
        return self.get_by_field("openid", openid)

    def get_by_phone(self, phone: str) -> User | None:
        """根据手机号查询用户"""
        return self.get_by_field("phone", phone)
