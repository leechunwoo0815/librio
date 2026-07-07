# backend/domain/admin/routers/admin_reports_router.py
"""报告管理路由"""

from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import (
    get_db,
    get_admin_report_service,
    get_admin_refund_service,
)
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN, ROLE_STAFF
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    PaginatedResponse,
    ReadingStatsResponse,
    ReadingTrendsResponse,
    AuditRefundRequest,
    AddObservationCommentRequest,
)
from backend.domain.admin.services.refund_service import AdminRefundService
from backend.domain.admin.services.report_service import AdminReportService
from backend.domain.refund.service import RefundService
from backend.domain.refund.schemas import RefundAudit
from backend.domain.report.service import ReportService

router = APIRouter(prefix="/admin/api", tags=["报告管理"])


# ==================== 退款管理 ====================

@router.get("/refunds", response_model=PaginatedResponse)
def list_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    service: AdminRefundService = Depends(get_admin_refund_service),
):
    """获取退款列表 — 带分页"""
    return service.list_refunds(page, page_size)


@router.put("/refunds/{refund_id}/audit", response_model=SuccessResponse)
def audit_refund(
    refund_id: int,
    data: AuditRefundRequest,
    background_tasks: BackgroundTasks,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
    refund_service: AdminRefundService = Depends(get_admin_refund_service),
):
    """审核退款"""
    service = RefundService(db)
    status = 1 if data.action == "approve" else 2
    audit = RefundAudit(status=status, admin_id=admin.id, remark=data.comment)
    result = service.audit_refund(refund_id, audit)

    # 审核通过后，异步执行微信退款
    if data.action == "approve":
        refund, order = refund_service.get_refund_and_order(refund_id)
        if refund and order:
            background_tasks.add_task(service._execute_wechat_refund_async, refund, order)

    return result


# ==================== 报告管理 ====================

@router.get("/reports", response_model=PaginatedResponse)
def list_reports(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    service: AdminReportService = Depends(get_admin_report_service),
):
    """获取报告汇总列表（当前仅观察期报告） — 带分页"""
    return service.list_observation_reports(page, page_size, keyword)


@router.get("/reports/observation", response_model=PaginatedResponse)
def list_observation_reports(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    service: AdminReportService = Depends(get_admin_report_service),
):
    """获取观察期报告列表 — 带分页"""
    return service.list_observation_reports(page, page_size, keyword)


@router.post("/reports/observation/generate", response_model=SuccessResponse)
def generate_observation_report(
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """生成到期观察期报告"""
    service = ReportService(db)
    generated = service.generate_due_reports()
    return {"success": True, "message": f"已生成 {len(generated)} 份观察期报告"}


@router.put("/reports/observation/{report_id}/comment", response_model=SuccessResponse)
def add_observation_comment(
    report_id: int,
    data: AddObservationCommentRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """添加观察期评语"""
    service = ReportService(db)
    return service.add_teacher_comment(report_id, admin.id, data.comment)


# ==================== 阅读数据统计 ====================

@router.get("/reading-data/stats", response_model=ReadingStatsResponse)
def get_reading_stats(
    period: str = Query("today", pattern="^(today|week|month|all)$"),
    admin=Depends(get_current_admin),
    service: AdminReportService = Depends(get_admin_report_service),
):
    """获取阅读数据统计 — 使用 SQL 聚合"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        start_date = today_start.strftime("%Y-%m-%d")
    elif period == "week":
        start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "month":
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
    else:
        start_date = None

    return service.get_reading_stats(start_date)


@router.get("/reading-data/trends", response_model=ReadingTrendsResponse)
def get_reading_trends(
    days: int = Query(14, ge=7, le=30),
    admin=Depends(get_current_admin),
    service: AdminReportService = Depends(get_admin_report_service),
):
    """获取阅读趋势数据 — 使用 SQL 聚合"""
    now = datetime.now()
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    return service.get_reading_trends(start_date, end_date)
