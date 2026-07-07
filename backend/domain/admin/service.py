# backend/domain/admin/service.py
"""管理域业务逻辑 — AdminService 已逐步拆分为多个子 Service。

本文件保留 AdminService 空类，作为兼容锚点；新的管理端路由请使用
backend.domain.admin.services 下的专用 Service。
"""

from sqlalchemy.orm import Session


class AdminService:
    """管理服务（已拆分）：请勿新增方法，请按域新建/使用 AdminXxxService。"""

    def __init__(self, db: Session):
        self.db = db
