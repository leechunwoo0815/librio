# backend/domain/admin/admin_page_router.py
"""管理端页面路由 — 服务 Jinja2 HTML 模板"""

import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

_template_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
templates = Jinja2Templates(directory=_template_dir)

router = APIRouter(prefix="/admin/view", tags=["管理页面"])


def _get_token_from_request(request: Request) -> str | None:
    """从请求中提取 Bearer token（优先从 header，其次从 cookie）"""
    # 1. 先检查 Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # 2. 再检查 cookie
    token = request.cookies.get("mw_admin_token")
    if token:
        return token
    return None


def _validate_admin_token(token: str) -> dict | None:
    """验证 admin token，返回 admin 信息或 None"""
    from jose import JWTError, jwt
    from backend.config import get_settings
    from backend.domain.admin.models import Admin
    from backend.database import get_session

    settings = get_settings()
    db = None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "admin":
            return None
        admin_id = payload.get("sub")
        if not admin_id:
            return None

        SessionLocal = get_session()
        db = SessionLocal()
        admin = db.query(Admin).filter(
            Admin.id == int(admin_id),
            Admin.is_deleted == 0,
            Admin.status == Admin.STATUS_ACTIVE,
        ).first()
        if not admin:
            return None
        return {"id": admin.id, "name": admin.name or admin.username, "role": admin.role}
    except (JWTError, Exception):
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


# 登录页（无 sidebar）
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html")


# ===== 运营 =====
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/dashboard.html", {"active_page": "dashboard"}
    )


@router.get("/users", response_class=HTMLResponse)
async def users(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/users.html", {"active_page": "users"}
    )


@router.get("/orders", response_class=HTMLResponse)
async def orders(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/orders.html", {"active_page": "orders"}
    )


@router.get("/submissions", response_class=HTMLResponse)
async def submissions(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/submissions.html", {"active_page": "submissions"}
    )


@router.get("/borrow", response_class=HTMLResponse)
async def borrow(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/borrow.html", {"active_page": "borrow"}
    )


@router.get("/activities", response_class=HTMLResponse)
async def activities(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/activities.html", {"active_page": "activities"}
    )


@router.get("/activity-checkin", response_class=HTMLResponse)
async def activity_checkin(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/activity_checkin.html", {"active_page": "activity-checkin"}
    )


# ===== 场馆 =====
@router.get("/venues", response_class=HTMLResponse)
async def venues(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/venues.html", {"active_page": "venues"}
    )


@router.get("/teachers", response_class=HTMLResponse)
async def teachers(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/teachers.html", {"active_page": "teachers"}
    )


# ===== 评估 =====
@router.get("/assessments", response_class=HTMLResponse)
async def assessments(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/assessments.html", {"active_page": "assessments"}
    )


# ===== 内容 =====
@router.get("/books", response_class=HTMLResponse)
async def books(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/books.html", {"active_page": "books"}
    )


@router.get("/library", response_class=HTMLResponse)
async def library(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/books.html", {"active_page": "library"}
    )


@router.get("/bookcopy", response_class=HTMLResponse)
async def bookcopy(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/bookcopy.html", {"active_page": "bookcopy"}
    )


@router.get("/content", response_class=HTMLResponse)
async def content(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/content.html", {"active_page": "content"}
    )


@router.get("/dictionary", response_class=HTMLResponse)
async def dictionary(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/dictionary.html", {"active_page": "dictionary"}
    )


@router.get("/questions", response_class=HTMLResponse)
async def questions(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/questions.html", {"active_page": "questions"}
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/reports.html", {"active_page": "reports"}
    )


@router.get("/audio", response_class=HTMLResponse)
async def audio(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/audio.html", {"active_page": "audio"}
    )


# ===== 财务 =====
@router.get("/deposit", response_class=HTMLResponse)
async def deposit(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/deposit.html", {"active_page": "deposit"}
    )


@router.get("/reservation", response_class=HTMLResponse)
async def reservation(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/reservation.html", {"active_page": "reservation"}
    )


# ===== 系统 =====
@router.get("/levels", response_class=HTMLResponse)
async def levels(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/levels.html", {"active_page": "levels"}
    )


@router.get("/achievements", response_class=HTMLResponse)
async def achievements(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/achievements.html", {"active_page": "achievements"}
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/settings.html", {"active_page": "settings"}
    )


# ===== 系统（扩展） =====
@router.get("/logs", response_class=HTMLResponse)
async def operation_logs(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/operation_logs.html", {"active_page": "operation-logs"}
    )


@router.get("/trash", response_class=HTMLResponse)
async def recycle_bin(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/recycle_bin.html", {"active_page": "recycle-bin"}
    )


# ===== 个人名片 =====
@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/profile.html", {"active_page": "profile"}
    )


# ===== 出卷 =====
@router.get("/quiz", response_class=HTMLResponse)
async def quiz(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/quiz.html", {"active_page": "quiz"}
    )


# ===== 阅读数据 =====
@router.get("/reading-data", response_class=HTMLResponse)
async def reading_data(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/reading_data.html", {"active_page": "reading-data"}
    )


# ===== 晋级证书 =====
@router.get("/certificates", response_class=HTMLResponse)
async def certificates(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/certificates.html", {"active_page": "certificates"}
    )


# ===== 运营消息 =====
@router.get("/messages", response_class=HTMLResponse)
async def messages(request: Request):
    admin = _get_admin_info(request)
    if not admin:
        return RedirectResponse(url="/admin/view/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/message_manage.html", {"active_page": "messages"}
    )
