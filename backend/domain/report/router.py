# backend/domain/report/router.py
"""报告域 API 路由 — 学习报告/观察期报告/阅读统计"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from backend.common.dependencies import get_report_service
from backend.domain.report.schemas import (
    ObservationReportResponse,
    LearningReportResponse,
    ObservationReportDetailResponse,
    GenerateReportsResponse,
    MarkViewedResponse,
    AddCommentResponse,
    SummaryResponse,
    TodayStatsResponse,
    TrendEntryResponse,
    WeeklyReportResponse,
)
from backend.domain.report.service import ReportService
from backend.middleware.admin_rbac import require_perm
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import GetOwnedChild, GetOwnedChildFromQuery

router = APIRouter(prefix="/report", tags=["报告"])


# ==================== 阅读统计 ====================
# (放在前面，避免路径参数冲突)


@router.get("/stats/summary", response_model=SummaryResponse)
def get_stats_summary(
    child=Depends(GetOwnedChildFromQuery()),
    service: ReportService = Depends(get_report_service),
):
    """累计统计"""
    return service.get_summary(child.id)


@router.get("/stats/today", response_model=TodayStatsResponse)
def get_today_stats(
    child=Depends(GetOwnedChildFromQuery()),
    service: ReportService = Depends(get_report_service),
):
    """今日统计"""
    return service.get_today_stats(child.id)


@router.get("/stats/trend", response_model=list[TrendEntryResponse])
def get_reading_trend(
    days: int = Query(7, ge=1, le=90),
    child=Depends(GetOwnedChildFromQuery()),
    service: ReportService = Depends(get_report_service),
):
    """阅读趋势（最近N天）"""
    return service.get_trend(child.id, days)


@router.get("/stats/weekly", response_model=WeeklyReportResponse)
def get_weekly_report(
    child=Depends(GetOwnedChildFromQuery()),
    service: ReportService = Depends(get_report_service),
):
    """生成周报"""
    return service.generate_weekly_report(child.id)


# ==================== 学习报告 ====================


@router.get("/observation/{child_id}", response_model=ObservationReportResponse | None)
def get_observation_report(
    child=Depends(GetOwnedChild()),
    service: ReportService = Depends(get_report_service),
):
    """获取孩子的观察期报告（简版）"""
    return service.get_observation_report(child.id)


@router.get(
    "/observation/{child_id}/detail",
    response_model=ObservationReportDetailResponse | None,
)
def get_observation_report_detail(
    child=Depends(GetOwnedChild()),
    service: ReportService = Depends(get_report_service),
):
    """获取孩子的观察期报告详情"""
    return service.get_observation_report_detail(child.id)


@router.post("/observation/generate", response_model=GenerateReportsResponse)
def generate_observation_reports(
    service: ReportService = Depends(get_report_service),
    admin=Depends(require_perm("report.generate")),
):
    """手动触发生成到期的观察期报告"""
    return service.generate_due_reports()


@router.put("/observation/{report_id}/viewed", response_model=MarkViewedResponse)
def mark_observation_viewed(
    report_id: int,
    service: ReportService = Depends(get_report_service),
    current_user=Depends(get_current_user),
):
    """标记报告已查看"""
    return service.mark_observation_viewed(report_id)


@router.put("/observation/{report_id}/comment", response_model=AddCommentResponse)
def add_observation_comment(
    report_id: int,
    comment: str = Query(...),
    service: ReportService = Depends(get_report_service),
    admin=Depends(require_perm("report.comment")),
):
    """老师添加评语"""
    return service.add_teacher_comment(report_id, admin.id, comment)


@router.get("/observation/{child_id}/html")
def get_observation_report_html(
    child=Depends(GetOwnedChild()),
    service: ReportService = Depends(get_report_service),
):
    """获取观察期报告HTML（可渲染为PDF）"""
    html = service.render_report_html(child.id)
    if not html:
        from backend.common.exceptions import NotFoundError

        raise NotFoundError("暂无观察期报告")
    return HTMLResponse(content=html)


@router.get("/observation/{child_id}/pdf")
async def get_observation_report_pdf(
    child=Depends(GetOwnedChild()),
    service: ReportService = Depends(get_report_service),
):
    """获取观察期报告PDF"""
    pdf = await service.render_report_pdf(child.id)
    if not pdf:
        from backend.common.exceptions import NotFoundError

        raise NotFoundError("暂无观察期报告")
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=observation_report_{child.id}.pdf"
        },
    )


@router.get("/learning/{child_id}", response_model=LearningReportResponse | None)
def get_learning_report(
    child=Depends(GetOwnedChild()),
    service: ReportService = Depends(get_report_service),
):
    """获取孩子的学习报告"""
    return service.get_learning_report(child.id)
