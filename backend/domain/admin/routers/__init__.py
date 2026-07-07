# backend/domain/admin/routers/__init__.py
"""管理端路由模块"""

from backend.domain.admin.routers.admin_venues_router import router as venues_router
from backend.domain.admin.routers.admin_teachers_router import router as teachers_router
from backend.domain.admin.routers.admin_books_router import router as books_router
from backend.domain.admin.routers.admin_advancement_router import router as advancement_router
from backend.domain.admin.routers.admin_activities_router import router as activities_router
from backend.domain.admin.routers.admin_borrow_router import router as borrow_router
from backend.domain.admin.routers.admin_reports_router import router as reports_router
from backend.domain.admin.routers.admin_system_router import router as system_router

__all__ = [
    "venues_router",
    "teachers_router",
    "books_router",
    "advancement_router",
    "activities_router",
    "borrow_router",
    "reports_router",
    "system_router",
]
