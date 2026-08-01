# backend/domain/admin/routers/admin_teacher_workbench_router.py
"""D1 老师工作台 + D2 课后反馈路由"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.common.exceptions import ForbiddenError
from backend.database import get_db
from backend.domain.admin.admin_schemas import AdminActionResponse
from backend.domain.admin.services.teacher_workbench_service import (
    TeacherWorkbenchService,
)
from backend.middleware.admin_rbac import require_perm

router = APIRouter(prefix="/admin/api/teacher", tags=["老师工作台"])


def _teacher_id_of(admin) -> int:
    """当前管理员账号关联的老师ID（老师角色必须关联）"""
    teacher_id = getattr(admin, "teacher_id", None)
    if not teacher_id:
        raise ForbiddenError("该账号未关联老师，无法使用老师工作台")
    return teacher_id


@router.get("/workbench", response_model=AdminActionResponse)
def get_workbench(
    db: Session = Depends(get_db),
    admin=Depends(require_perm("dashboard.view")),
):
    """D1 老师工作台：今日课程 / 待审核提交 / 负责孩子近况 / 最近指导"""
    return TeacherWorkbenchService(db).get_workbench(_teacher_id_of(admin))


class FeedbackRequest(BaseModel):
    child_id: int = Field(..., description="孩子ID")
    content: str = Field(..., min_length=1, max_length=500, description="反馈内容")


@router.post("/feedback", response_model=AdminActionResponse, status_code=201)
def post_feedback(
    data: FeedbackRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_perm("report.comment")),
):
    """D2 课后反馈：写指导记录 + 推送家长（老师消息）"""
    return TeacherWorkbenchService(db).post_feedback(
        _teacher_id_of(admin), data.child_id, data.content, admin.id
    )
