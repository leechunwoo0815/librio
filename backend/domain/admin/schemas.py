# backend/domain/admin/schemas.py
"""兼容层 — 所有 Schema 已迁移到 admin_schemas.py

此文件仅用于保持向后兼容，所有新代码应直接从 admin_schemas.py 导入。
"""

from backend.domain.admin.admin_schemas import *  # noqa: F401,F403
