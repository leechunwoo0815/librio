# backend/main.py
"""
[What] FastAPI应用入口
[Why] 所有路由、中间件、异常处理器在此注册
[How] 创建FastAPI实例，注册路由和中间件

架构意图：
  - 极简入口，只做挂载，不写业务逻辑
  - 全局异常处理器统一转换 BusinessException → HTTP 响应
  - CORS 严格限定允许的域名（生产环境关闭 allow_origins=["*"]）
  - 生产环境关闭 Swagger 文档（docs_url=None）
  - 路由全部来自 domain 层，不再使用旧 routers 目录
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.common.exceptions import BusinessException, business_exception_handler
from backend.config import get_settings
from backend.middleware.trace import trace_middleware
from backend.middleware.request_log import RequestLogMiddleware

from starlette.staticfiles import StaticFiles

settings = get_settings()

log_level = logging.DEBUG if settings.DEBUG else logging.INFO
logging.basicConfig(level=log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    启动时：
      - 注册领域事件处理器
      - 启动定时任务调度器
    关闭时：
      - 停止定时任务调度器
    """
    # 注册领域事件处理器
    from backend.bootstrap import register_event_handlers

    register_event_handlers()

    # 启动定时任务
    from backend.tasks.scheduler import init_scheduler, stop_scheduler

    init_scheduler(app)

    # 启动时刷新微信平台证书（生产环境）
    if not settings.DEBUG and getattr(settings, "WECHAT_PRIVATE_KEY_PATH", ""):
        try:
            from backend.integrations.wechat.pay_v3 import WeChatPayV3
            import asyncio

            pay = WeChatPayV3()
            asyncio.create_task(pay.refresh_platform_cert())
        except Exception as e:
            logger.warning(f"Platform cert refresh failed on startup: {e}")

    # MOCK_SMS 警告（避免生产环境长期遗忘切换真实短信）
    if not settings.DEBUG and settings.MOCK_SMS:
        logger.warning("MOCK_SMS=true — 短信验证码使用 mock 网关，不会实际发送短信")
        logger.warning("请及时接入真实短信 SDK（tencent/aliyun）并设置 MOCK_SMS=false")

    yield
    stop_scheduler()


# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    # 生产环境关闭 Swagger 文档
    docs_url=None if not settings.DEBUG else "/docs",
    redoc_url=None if not settings.DEBUG else "/redoc",
    lifespan=lifespan,
)

# ============================================================
# 全局异常处理器
# Service 层 raise NotFoundError("订单不存在")
# → 自动转换为 HTTP 404 {"detail": "订单不存在"}
# Router 层不再需要 try/except
# ============================================================
app.add_exception_handler(BusinessException, business_exception_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局未捕获异常处理器 — 防止返回原始 500 HTML 页面"""
    logger.error("Unhandled exception: %s %s - %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


# ============================================================
# 中间件注册
# ============================================================


# TraceID 中间件 — 最先执行，确保所有后续处理都有 TraceID
@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    """禁止缓存 HTML 和 JS/CSS 文件（开发环境）"""
    response = await trace_middleware(request, call_next)
    path = request.url.path
    if path.endswith('.html') or path.endswith('.js') or path.endswith('.css') or '/admin/view/' in path:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# CORS 中间件 — 严格限定允许的域名
# 微信小程序请求来源是 servicewechat.com
CORS_ORIGINS = ["https://servicewechat.com"]
if settings.DEBUG:
    CORS_ORIGINS.extend([
        "http://localhost:3000",
        "http://localhost:3002",
        "http://localhost:5173",
        "http://localhost:8002",
        "http://127.0.0.1:8002",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-ID"],
)

# 请求日志中间件 — 记录所有请求与异常，便于排查浏览器端问题
app.add_middleware(RequestLogMiddleware)


# ============================================================
# 路由注册 — 领域驱动架构（domain 层）
# 所有路由来自 backend.domain.*，不再使用旧 backend.routers
# ============================================================

# 核心域
from backend.domain.user.router import router as user_router  # noqa: E402
from backend.domain.child.router import router as child_router  # noqa: E402
from backend.domain.book.router import router as book_router  # noqa: E402
from backend.domain.bookshelf.router import (  # noqa: E402
    router as bookshelf_router,
    fav_router as bookshelf_fav_router,
)
from backend.domain.reading.router import router as reading_router  # noqa: E402
from backend.domain.vocabulary.router import router as vocabulary_router  # noqa: E402
from backend.domain.advancement.router import router as advancement_router  # noqa: E402

# 交易域
from backend.domain.order.router import router as order_router  # noqa: E402
from backend.domain.refund.router import router as refund_router  # noqa: E402

# OMO 域（V3.1）
from backend.domain.borrow.router import router as borrow_router  # noqa: E402
from backend.domain.deposit.router import router as deposit_router  # noqa: E402
from backend.domain.reservation.router import router as reservation_router  # noqa: E402

# 辅助域
from backend.domain.report.router import router as report_router  # noqa: E402
from backend.domain.certificate.router import router as certificate_router  # noqa: E402
from backend.domain.profile.router import router as profile_router  # noqa: E402
from backend.domain.activity.router import router as activity_router  # noqa: E402
from backend.domain.admin.admin_auth_router import router as admin_auth_router  # noqa: E402
from backend.domain.admin.admin_page_router import router as admin_page_router  # noqa: E402
from backend.domain.parent_course_time.router import (  # noqa: E402
    router as parent_course_router,
)
from backend.domain.evaluation.router import router as evaluation_router  # noqa: E402
from backend.domain.assessment.router import router as assessment_router  # noqa: E402
from backend.domain.dictionary.router import router as dictionary_router  # noqa: E402
from backend.domain.audio.router import router as audio_router  # noqa: E402
from backend.domain.security.router import router as security_router  # noqa: E402
from backend.domain.wechat.router import router as wechat_router  # noqa: E402

app.include_router(user_router)
app.include_router(child_router)
app.include_router(book_router)
app.include_router(bookshelf_router)
app.include_router(bookshelf_fav_router)
app.include_router(reading_router)
app.include_router(vocabulary_router)
app.include_router(advancement_router)
app.include_router(order_router)
app.include_router(refund_router)
app.include_router(borrow_router)
app.include_router(deposit_router)
app.include_router(reservation_router)
app.include_router(report_router)
app.include_router(certificate_router)
app.include_router(profile_router)
app.include_router(activity_router)
app.include_router(parent_course_router)
app.include_router(evaluation_router)
app.include_router(assessment_router)
app.include_router(dictionary_router)
app.include_router(audio_router)
app.include_router(security_router)
app.include_router(wechat_router)

# 消息域
from backend.domain.message.router import router as message_router  # noqa: E402

app.include_router(message_router)

# 管理端路由 — 页面路由优先注册（HTML 页面），API 路由后注册（JSON 响应）

# 新的领域路由（拆分后）
from backend.domain.admin.routers.admin_venues_router import router as admin_venues_router  # noqa: E402
from backend.domain.admin.routers.admin_teachers_router import router as admin_teachers_router  # noqa: E402
from backend.domain.admin.routers.admin_books_router import router as admin_books_router  # noqa: E402
from backend.domain.admin.routers.admin_advancement_router import router as admin_advancement_router  # noqa: E402
from backend.domain.admin.routers.admin_activities_router import router as admin_activities_router  # noqa: E402
from backend.domain.admin.routers.admin_borrow_router import router as admin_borrow_router  # noqa: E402
from backend.domain.admin.routers.admin_reports_router import router as admin_reports_router  # noqa: E402
from backend.domain.admin.routers.admin_system_router import router as admin_system_router  # noqa: E402
from backend.domain.admin.routers.admin_role_router import router as admin_role_router  # noqa: E402
from backend.domain.admin.routers.admin_benefit_transfer_router import router as admin_benefit_transfer_router  # noqa: E402

app.include_router(admin_page_router)  # HTML 页面路由（优先匹配）
app.include_router(admin_auth_router)  # 认证 API 路由

# 领域路由
app.include_router(admin_venues_router)
app.include_router(admin_teachers_router)
app.include_router(admin_books_router)
app.include_router(admin_advancement_router)
app.include_router(admin_activities_router)
app.include_router(admin_borrow_router)
app.include_router(admin_reports_router)
app.include_router(admin_system_router)
app.include_router(admin_role_router)
app.include_router(admin_benefit_transfer_router)

# ============================================================
# Mock 辅助路由（仅本地开发环境注册）
# ============================================================
if settings.MOCK_PAYMENT and settings.DEBUG:
    from backend.common.gateways.payment.mock_routes import mock_payment_router

    app.include_router(mock_payment_router)
    logger.warning("MOCK_PAYMENT 已启用 — 仅限本地开发，生产环境必须关闭")

if settings.MOCK_SMS and settings.DEBUG:
    from backend.common.gateways.sms.mock_routes import mock_sms_router

    app.include_router(mock_sms_router)
    logger.warning("MOCK_SMS 已启用 — 仅限本地开发，生产环境必须关闭")


# ============================================================
# 健康检查端点
# ============================================================
@app.get("/health")
def health_check():
    """健康检查端点 — 供负载均衡器和监控系统使用"""
    return {"status": "ok", "version": settings.APP_VERSION}


# 静态文件
import os  # noqa: E402

_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

_uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(_uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")


# ============================================================
# 健康检查
# ============================================================


@app.get("/")
async def root():
    """根路径"""
    return {"message": "DmkWords API is running", "version": settings.APP_VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app", host="0.0.0.0", port=settings.BACKEND_PORT, reload=True
    )
