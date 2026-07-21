# backend/domain/admin/admin_page_router.py
"""管理端页面路由 — 服务 Jinja2 HTML 模板"""

import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from backend.database import get_session
from backend.domain.admin.services.account_service import AdminAccountService

_template_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
templates = Jinja2Templates(directory=_template_dir)

router = APIRouter(prefix="/admin/view", tags=["管理页面"])

# 页面权限映射 — 每个页面需要的最低权限
PAGE_PERM_MAP: dict[str, str] = {
    "dashboard": "dashboard.view",
    "users": "user.list",
    "orders": "order.list",
    "submissions": "submission.list",
    "borrow": "borrow.list",
    "activities": "activity.list",
    "activity-checkin": "activity.checkin",
    "venues": "venue.list",
    "teachers": "teacher.list",
    "assessments": "assessment.list",
    "books": "book.list",
    "library": "book.list",
    "bookcopy": "bookcopy.list",
    "content": "content.list",
    "dictionary": "dictionary.list",
    "questions": "question.list",
    "reports": "report.list",
    "audio": "content.list",
    "deposit": "deposit.list",
    "reservation": "reservation.list",
    "levels": "level.list",
    "achievements": "achievement.list",
    "settings": "config.view",
    "operation-logs": "log.list",
    "recycle_bin": "recycle.list",
    "profile": "",
    "quiz": "quiz.list",
    "reading-data": "report.reading_data",
    "certificates": "certificate.list",
    "messages": "message.list",
    "roles": "role.list",
    "benefit-transfers": "benefit_transfer.list",
    "damage-reports": "book_damage.list",
}


def _get_token_from_request(request: Request) -> str | None:
    """从请求中提取 Bearer token（优先从 header，其次从 cookie）"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    token = request.cookies.get("mw_admin_token")
    if token:
        return token
    return None


def _validate_admin_token(token: str) -> dict | None:
    """验证 admin token，返回 admin 信息或 None — 委托给 Service 层执行"""
    db = None
    try:
        SessionLocal = get_session()
        db = SessionLocal()
        return AdminAccountService(db).validate_admin_token(token)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to validate admin token")
        return None
    finally:
        if db:
            db.close()


def _get_admin_info(request: Request) -> dict | None:
    """从请求中获取管理员信息，失败返回 None"""
    token = _get_token_from_request(request)
    if not token:
        return None
    return _validate_admin_token(token)


def _check_page_perm(admin: dict, page: str) -> bool:
    """检查管理员是否有权访问页面"""
    required_perm = PAGE_PERM_MAP.get(page)
    if not required_perm:
        return True
    perms = admin.get("permissions", [])
    return required_perm in perms


def _render_page(
    request: Request, page: str, template: str | None = None, extra: dict | None = None
):
    """统一页面渲染 — 带权限校验"""
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)

    if not _check_page_perm(admin, page):
        return RedirectResponse(url="/admin/view/403", status_code=302)

    permissions = admin.get("permissions", [])
    ctx = {
        "active_page": page,
        "admin": admin,
        "user_can": lambda code: code in permissions,
    }
    if extra:
        ctx.update(extra)
    return templates.TemplateResponse(request, template or f"admin/{page}.html", ctx)


# 登录页（无 sidebar）
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html")


# ===== 运营 =====
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _render_page(request, "dashboard")


@router.get("/users", response_class=HTMLResponse)
async def users(request: Request):
    return _render_page(request, "users")


@router.get("/orders", response_class=HTMLResponse)
async def orders(request: Request):
    return _render_page(request, "orders")


@router.get("/submissions", response_class=HTMLResponse)
async def submissions(request: Request):
    return _render_page(request, "submissions")


@router.get("/borrow", response_class=HTMLResponse)
async def borrow(request: Request):
    return _render_page(request, "borrow")


@router.get("/activities", response_class=HTMLResponse)
async def activities(request: Request):
    return _render_page(request, "activities")


@router.get("/activity-checkin", response_class=HTMLResponse)
async def activity_checkin(request: Request):
    return _render_page(request, "activity-checkin")


# ===== 场馆 =====
@router.get("/venues", response_class=HTMLResponse)
async def venues(request: Request):
    return _render_page(request, "venues")


@router.get("/teachers", response_class=HTMLResponse)
async def teachers(request: Request):
    return _render_page(request, "teachers")


# ===== 评估 =====
@router.get("/assessments", response_class=HTMLResponse)
async def assessments(request: Request):
    return _render_page(request, "assessments")


# ===== 内容 =====
@router.get("/books", response_class=HTMLResponse)
async def books(request: Request):
    return _render_page(request, "books")


@router.get("/library", response_class=HTMLResponse)
async def library(request: Request):
    return _render_page(request, "library")


@router.get("/bookcopy", response_class=HTMLResponse)
async def bookcopy(request: Request):
    return _render_page(request, "bookcopy")


@router.get("/content", response_class=HTMLResponse)
async def content(request: Request):
    return _render_page(request, "content")


@router.get("/dictionary", response_class=HTMLResponse)
async def dictionary(request: Request):
    return _render_page(request, "dictionary")


@router.get("/questions", response_class=HTMLResponse)
async def questions(request: Request):
    return _render_page(request, "questions")


@router.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    return _render_page(request, "reports")


@router.get("/audio", response_class=HTMLResponse)
async def audio(request: Request):
    return _render_page(request, "audio")


# ===== 财务 =====
@router.get("/deposit", response_class=HTMLResponse)
async def deposit(request: Request):
    return _render_page(request, "deposit")


@router.get("/reservation", response_class=HTMLResponse)
async def reservation(request: Request):
    return _render_page(request, "reservation")


# ===== 系统 =====
@router.get("/levels", response_class=HTMLResponse)
async def levels(request: Request):
    return _render_page(request, "levels")


@router.get("/achievements", response_class=HTMLResponse)
async def achievements(request: Request):
    return _render_page(request, "achievements")


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    return _render_page(request, "settings")


# ===== 系统（扩展） =====
@router.get("/logs", response_class=HTMLResponse)
async def operation_logs(request: Request):
    return _render_page(request, "operation-logs")


@router.get("/recycle-bin", response_class=HTMLResponse)
async def recycle_bin(request: Request):
    return _render_page(request, "recycle_bin")


# ===== 个人名片 =====
@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    return _render_page(request, "profile")


# ===== 出卷 =====
@router.get("/quiz", response_class=HTMLResponse)
async def quiz(request: Request):
    return _render_page(request, "quiz")


# ===== 阅读数据 =====
@router.get("/reading-data", response_class=HTMLResponse)
async def reading_data(request: Request):
    return _render_page(request, "reading-data")


# ===== 晋级证书 =====
@router.get("/certificates", response_class=HTMLResponse)
async def certificates(request: Request):
    return _render_page(request, "certificates")


# ===== 运营消息 =====
@router.get("/messages", response_class=HTMLResponse)
async def messages(request: Request):
    return _render_page(request, "messages")


# ===== 角色管理 =====
@router.get("/roles", response_class=HTMLResponse)
async def roles(request: Request):
    return _render_page(request, "roles")


# ===== 权益转让审核 =====
@router.get("/benefit-transfers", response_class=HTMLResponse)
async def benefit_transfers(request: Request):
    return _render_page(request, "benefit-transfers")


# ===== 图书损坏定责 =====
@router.get("/damage-reports", response_class=HTMLResponse)
async def damage_reports(request: Request):
    return _render_page(request, "damage-reports")


# ===== 权限不足页面 =====
@router.get("/403", response_class=HTMLResponse)
async def forbidden_page(request: Request):
    return _render_page(request, "403")
