# backend/domain/profile/repository.py
"""名片域数据访问层 — 聚合查询域，无独立表"""

from sqlalchemy.orm import Session


class ProfileRepository:
    """名片仓库 — 聚合其他域的数据"""

    def __init__(self, db: Session):
        self.db = db
