# backend/domain/admin/routers/admin_advancement_router.py
"""晋级管理路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import get_db, get_admin_book_service
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN, ROLE_STAFF
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    CreateLevelRequest,
    UpdateLevelRequest,
    CreateAchievementRequest,
    UpdateAchievementRequest,
    ReviewSubmissionRequest,
    CreateQuestionRequest,
    UpdateQuestionRequest,
    BulkImportQuestionItem,
)
from backend.domain.advancement.service import AdvancementService
from backend.domain.admin.services.book_service import AdminBookService

router = APIRouter(prefix="/admin/api/advancement", tags=["晋级管理"])


# ==================== 级别管理 ====================

@router.get("/levels", response_model=list)
def list_levels(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取级别列表"""
    service = AdvancementService(db)
    return service.get_levels()


@router.post("/levels", response_model=AdminActionResponse, status_code=201)
def create_level(
    data: CreateLevelRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """创建级别"""
    service = AdvancementService(db)
    return service.create_level(data)


@router.put("/levels/{level_id}", response_model=SuccessResponse)
def update_level(
    level_id: int,
    data: UpdateLevelRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """更新级别"""
    service = AdvancementService(db)
    return service.update_level(level_id, data)


@router.delete("/levels/{level_id}", response_model=SuccessResponse)
def delete_level(
    level_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """删除级别"""
    service = AdvancementService(db)
    return service.delete_level(level_id)


# ==================== 成就管理 ====================

@router.get("/achievements", response_model=list)
def list_achievements(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取成就列表"""
    service = AdvancementService(db)
    return service.get_achievements()


@router.post("/achievements", response_model=AdminActionResponse, status_code=201)
def create_achievement(
    data: CreateAchievementRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """创建成就"""
    service = AdvancementService(db)
    return service.create_achievement(data)


@router.put("/achievements/{achievement_id}", response_model=SuccessResponse)
def update_achievement(
    achievement_id: int,
    data: UpdateAchievementRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """更新成就"""
    service = AdvancementService(db)
    return service.update_achievement(achievement_id, data)


@router.delete("/achievements/{achievement_id}", response_model=SuccessResponse)
def delete_achievement(
    achievement_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """删除成就"""
    service = AdvancementService(db)
    return service.delete_achievement(achievement_id)


@router.get("/achievements/records", response_model=AdminActionResponse)
def list_achievement_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取成就记录 — 带分页"""
    service = AdvancementService(db)
    return service.list_achievement_records(page, page_size)


# ==================== 证书管理 ====================

@router.get("/certificates", response_model=AdminActionResponse)
def list_certificates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取证书列表"""
    service = AdvancementService(db)
    return service.list_certificates(page, page_size)


@router.post("/certificates/{certificate_id}/regenerate", response_model=AdminActionResponse)
def regenerate_certificate(
    certificate_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """重新生成证书"""
    service = AdvancementService(db)
    return service.regenerate_certificate(certificate_id)


@router.delete("/certificates/{certificate_id}", response_model=AdminActionResponse)
def delete_certificate(
    certificate_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """删除证书"""
    service = AdvancementService(db)
    return service.delete_certificate(certificate_id)


# ==================== 提交审核 ====================

@router.get("/submissions", response_model=AdminActionResponse)
def list_submissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = None,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取审核列表 — 带分页"""
    service = AdvancementService(db)
    return service.list_submissions(page, page_size, status)


@router.put("/submissions/{submission_id}/review", response_model=AdminActionResponse)
def review_submission(
    submission_id: int,
    data: ReviewSubmissionRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """审核提交"""
    service = AdvancementService(db)
    return service.review_submission(submission_id, data)


# ==================== 题库管理 ====================

@router.get("/questions", response_model=AdminActionResponse)
def list_questions(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取题目列表 — 带分页"""
    service = AdvancementService(db)
    return service.list_questions(page, page_size, keyword)


@router.post("/questions", response_model=AdminActionResponse, status_code=201)
def create_question(
    data: CreateQuestionRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """创建题目"""
    service = AdvancementService(db)
    return service.create_question(data)


@router.put("/questions/{question_id}", response_model=AdminActionResponse)
def update_question(
    question_id: int,
    data: UpdateQuestionRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    db: Session = Depends(get_db),
):
    """更新题目"""
    service = AdvancementService(db)
    return service.update_question(question_id, data)


@router.delete("/questions/{question_id}", response_model=SuccessResponse)
def delete_question(
    question_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """删除题目"""
    service = AdvancementService(db)
    return service.delete_question(question_id)


@router.get("/questions/search", response_model=AdminActionResponse)
def search_questions_by_book(
    keyword: str = Query(..., description="书名或ISBN关键词"),
    admin=Depends(get_current_admin),
    service: AdminBookService = Depends(get_admin_book_service),
):
    """按书名/ISBN搜索题库"""
    return service.search_questions_by_book(keyword)


@router.post("/questions/bulk-import", response_model=AdminActionResponse)
def bulk_import_questions(
    questions: list[BulkImportQuestionItem],
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    service: AdminBookService = Depends(get_admin_book_service),
):
    """批量导入题目"""
    return service.bulk_import_questions(questions)
