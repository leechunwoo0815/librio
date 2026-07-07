# backend/domain/child/repository.py
"""孩子域数据访问层 — 继承 BaseRepository，扩展孩子特有查询"""

from sqlalchemy.orm import Session

from backend.common.base_repo import BaseRepository
from backend.domain.child.models import Child


class ChildRepository(BaseRepository[Child]):
    """孩子仓库 — 扩展按用户查询"""

    def __init__(self, db: Session):
        super().__init__(db, Child)

    def get_by_user_id(self, user_id: int) -> list[Child]:
        """获取用户下所有孩子"""
        return self.list_all(limit=100, user_id=user_id)
